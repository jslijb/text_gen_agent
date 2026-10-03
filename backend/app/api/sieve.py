"""sieve 抓取 API（对应 app/services/sieve_client.py 的契约）。

设计取舍：
- 创建 run 只做三件事：校验 → **落库（拿到 session_id 前的占位行）** → 交给 Celery。
  真正的 POST 在 worker 里跑，这样 key 永远不经过 HTTP 请求体、也不会被前端拿到。
- 未配置 SIEVE_API_KEY 时所有接口返回 503 + 明确文案，其它功能完全不受影响。
- `POST /runs` 与 `POST /runs/{id}/messages` 都是 202：任务已受理，结果靠轮询本地台账。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import settings
from app.models.sieve import SieveRun
from app.schemas.sieve import (
    SieveCreditsResponse,
    SieveRunListResponse,
    SieveRunOut,
    SieveRunRequest,
    SieveStatusResponse,
)
from app.services.sieve_client import (
    DEFAULT_COMPLIANCE_MODE,
    VALID_COMPLIANCE_MODES,
    SieveAmbiguousRequest,
    SieveAuthError,
    SieveClient,
    SieveError,
    SieveInsufficientCredits,
    SieveNotFound,
    SieveNotConfigured,
    SieveRateLimited,
    SieveRefused,
    SieveRequestRejected,
    SieveServerError,
    SieveTimeout,
    SieveTurnInFlight,
    SieveUnknownStatus,
    describe_conformance,
    validate_output_schema,
)

router = APIRouter(prefix="/sieve", tags=["sieve"])
logger = logging.getLogger(__name__)


def _map_error(e: SieveError, run_id: str | None = None) -> HTTPException:
    """Sieve* 异常 → HTTP 状态码（契约里的 400/401/402/404/409/429/5xx）。"""
    detail = str(e)
    if isinstance(e, SieveNotConfigured):
        return HTTPException(status_code=503, detail=detail)
    if isinstance(e, SieveRequestRejected):
        return HTTPException(status_code=400, detail=detail)
    if isinstance(e, SieveAuthError):
        return HTTPException(status_code=401, detail=detail)
    if isinstance(e, SieveInsufficientCredits):
        return HTTPException(status_code=402, detail=detail)
    if isinstance(e, SieveNotFound):
        return HTTPException(status_code=404, detail=detail)
    if isinstance(e, SieveTurnInFlight):
        return HTTPException(status_code=409, detail=detail)
    if isinstance(e, SieveRefused):
        return HTTPException(
            status_code=409,
            detail={"message": detail, "refusal": e.refusal, "run_id": run_id},
        )
    if isinstance(e, SieveRateLimited):
        return HTTPException(
            status_code=429,
            detail=detail,
            headers={"Retry-After": str(int(e.retry_after or 5))},
        )
    if isinstance(e, (SieveTimeout, SieveAmbiguousRequest, SieveUnknownStatus, SieveServerError)):
        return HTTPException(status_code=502, detail=detail)
    return HTTPException(status_code=502, detail=detail)


def _to_out(run: SieveRun) -> SieveRunOut:
    """行 → 响应。conformance 结论在这里算，前端不用自己判断 fail 能不能用。"""
    conformance = describe_conformance(
        {"status": run.schema_conformance} if run.schema_conformance else None
    )
    return SieveRunOut(
        id=str(run.id),
        session_id=run.session_id,
        status=run.status,
        kind=run.kind,
        parent_id=str(run.parent_id) if run.parent_id else None,
        instruction=run.instruction,
        target_urls=run.target_urls,
        compliance_mode=run.compliance_mode,
        turns=run.turns or 0,
        summary=run.summary,
        result=run.result,
        files=run.files,
        local_files=run.local_files,
        schema_conformance=run.schema_conformance,
        conformance_ok=conformance["ok"] if run.schema_conformance else None,
        conformance_warning=conformance["warning"] if run.schema_conformance else None,
        refusal_code=run.refusal_code,
        error=run.error,
        poll=f"/api/scrapes/{run.session_id}" if run.session_id else None,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get("/status", response_model=SieveStatusResponse)
async def sieve_status():
    """抓取能力是否可用（未配置 key 时前端据此隐藏入口）。"""
    client = SieveClient()
    return SieveStatusResponse(
        configured=client.configured,
        base_url=settings.SIEVE_BASE_URL,
        compliance_modes=list(VALID_COMPLIANCE_MODES),
    )


@router.post("/runs", response_model=SieveRunOut, status_code=202)
async def create_sieve_run(req: SieveRunRequest, db: Session = Depends(get_db)):
    """创建一次抓取。落库（占位行）→ 入队，session_id 由 worker 拿到后立刻落库。"""
    if not SieveClient().configured:
        raise _map_error(SieveNotConfigured("未配置 SIEVE_API_KEY，抓取功能未启用"))
    try:
        validate_output_schema(req.output_schema)
    except SieveError as e:
        raise _map_error(e)

    run = SieveRun(
        status=SieveRun.Status.STARTING,
        kind=SieveRun.Kind.SCRAPE,
        instruction=req.instruction,
        target_urls=req.target_urls or None,
        fields=req.fields or None,
        schema=req.schema_,
        output_schema=req.output_schema,
        table_shape=req.table_shape,
        compliance_mode=req.compliance_mode or DEFAULT_COMPLIANCE_MODE,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # 占位行已经落库，再交给 worker 去做 POST（失败/中断都能从这行恢复）
    from app.tasks.sieve_tasks import run_sieve_scrape_task
    run_sieve_scrape_task.delay(str(run.id))
    logger.info(f"sieve 抓取已受理: run_id={run.id} urls={len(req.target_urls or [])}")
    return _to_out(run)


@router.get("/runs", response_model=SieveRunListResponse)
async def list_sieve_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, description="按状态筛选：starting/running/done/refused/error"),
    db: Session = Depends(get_db),
):
    """本地 run 台账（含追问记录，按时间倒序）。"""
    query = db.query(SieveRun)
    if status:
        query = query.filter(SieveRun.status == status)
    total = query.count()
    rows = query.order_by(SieveRun.created_at.desc()).offset(offset).limit(limit).all()
    return SieveRunListResponse(items=[_to_out(r) for r in rows], total=total)


@router.get("/runs/{run_id}", response_model=SieveRunOut)
async def get_sieve_run(
    run_id: str,
    refresh: bool = Query(False, description="顺带向 sieve 拉一次最新状态（幂等 GET）"),
    db: Session = Depends(get_db),
):
    """查单个 run。`refresh=true` 时同步拉一次远端状态——worker 没在跑时也能看到进度。"""
    run = db.query(SieveRun).filter(SieveRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="run 不存在")

    if refresh and run.session_id:
        try:
            payload = SieveClient().get_scrape(run.session_id)
        except SieveError as e:
            raise _map_error(e, run_id=run_id)
        if payload.get("status"):
            run.status = SieveRun.Status.RUNNING
        if payload.get("turns") is not None:
            try:
                run.turns = int(payload["turns"])
            except (TypeError, ValueError):
                pass
        db.commit()
        db.refresh(run)
    return _to_out(run)


@router.post("/runs/{run_id}/messages", response_model=SieveRunOut, status_code=202)
async def send_sieve_message(run_id: str, req: SieveRunRequest, db: Session = Depends(get_db)):
    """追问。先记录 turn（新行 + baseline_turns 基线），再由 worker 轮询到 turns 推进。"""
    if not SieveClient().configured:
        raise _map_error(SieveNotConfigured("未配置 SIEVE_API_KEY，抓取功能未启用"))

    parent = db.query(SieveRun).filter(SieveRun.id == run_id).first()
    if parent is None:
        raise HTTPException(status_code=404, detail="run 不存在")
    if not parent.session_id:
        raise HTTPException(status_code=409, detail="该 run 还没有 session_id（可能仍在创建或创建结果不明）")
    try:
        validate_output_schema(req.output_schema)
    except SieveError as e:
        raise _map_error(e)

    run = SieveRun(
        status=SieveRun.Status.STARTING,
        kind=SieveRun.Kind.FOLLOW_UP,
        parent_id=parent.id,
        # 追问跑在父 run 的同一个远端会话上
        session_id=parent.session_id,
        instruction=req.instruction,
        target_urls=req.target_urls or None,
        fields=req.fields or None,
        schema=req.schema_,
        output_schema=req.output_schema,
        table_shape=req.table_shape,
        compliance_mode=req.compliance_mode or parent.compliance_mode or DEFAULT_COMPLIANCE_MODE,
        # 基线必须落库：轮询时 turns 会被远端值覆盖，补轮询要用这个原值判断"是否已推进"
        baseline_turns=parent.turns or 0,
        turns=parent.turns or 0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    from app.tasks.sieve_tasks import sieve_followup_task
    sieve_followup_task.delay(str(run.id))
    logger.info(f"sieve 追问已受理: parent={run_id} run_id={run.id} baseline_turns={run.baseline_turns}")
    return _to_out(run)


@router.get("/credits", response_model=SieveCreditsResponse)
async def sieve_credits():
    """额度查询（402 时用户最需要看到的东西）。"""
    try:
        payload = SieveClient().get_credits()
    except SieveError as e:
        raise _map_error(e)
    return SieveCreditsResponse(
        plan=payload.get("plan"),
        limit=payload.get("limit"),
        used=payload.get("used"),
        remaining=payload.get("remaining"),
        raw=payload,
    )
