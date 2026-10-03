"""sieve 抓取任务的 Celery 实现（复用项目既有的 Celery + SQLAlchemy 套路）。

三条硬规则，全部落在这一层：

1. **先落库再干活**。`SieveRun` 行先以 `starting` 提交，拿到 `session_id` 后立刻单独提交
   一次，然后才开始轮询。进程崩了，beat 的补轮询任务照着 `session_id` 接着跑，
   不会重复创建 run（重复扣费）。
2. **POST 超时不自动重试**。第一次调用可能已经成功，只有 429 / 5xx 才安全重试——
   这条规则在 `services/sieve_client.py` 里，任务层只负责把"结果不明"记成 `ambiguous`。
3. **单次任务的等待预算有限**（`POLL_BUDGET_SECONDS`，短于 celery 的 1800s 硬超时）。
   预算用完就把状态留在 `running` 返回，由补轮询任务接力，而不是被 SIGKILL。
"""
from __future__ import annotations

import logging

from celery import shared_task

from app.config.database import SessionLocal
from app.config.settings import settings
from app.models.sieve import SieveRun
from app.services.sieve_client import (
    SieveAmbiguousRequest,
    SieveAuthError,
    SieveClient,
    SieveError,
    SieveInsufficientCredits,
    SieveNotConfigured,
    SieveRefused,
    SieveTimeout,
    files_with_urls,
)

logger = logging.getLogger(__name__)

# 单个 worker 任务的轮询预算（秒）。celery task_time_limit=1800，留出余量给收尾与日志。
POLL_BUDGET_SECONDS = 1500
# 补轮询任务的批量上限，避免一次扫出太多任务把队列打满
RESUME_BATCH_SIZE = 20
# 同一 run 的轮询互斥锁（秒）；GET 本身幂等，锁只是省重复请求
POLL_LOCK_TTL = 900


def _redis_client(db_index: int = 1):
    """与 novel_tasks 一致：复用 broker 所在 Redis，单独开一把锁。"""
    from app.config.celery_config import celery_app
    import redis as redis_lib
    broker = celery_app.conf.broker_url.replace("redis://", "").split("/")[0]
    return redis_lib.Redis.from_url(f"redis://{broker}/{db_index}")


def _acquire_poll_lock(run_id: str) -> bool:
    """拿 run 级轮询锁；Redis 不可用时放行（不让基础设施故障挡住抓取）。"""
    try:
        return bool(_redis_client().set(f"sieve:poll_lock:{run_id}", "1", nx=True, ex=POLL_LOCK_TTL))
    except Exception as e:
        logger.warning(f"sieve 轮询锁获取失败，按放行处理: {e}")
        return True


def _release_poll_lock(run_id: str) -> None:
    try:
        _redis_client().delete(f"sieve:poll_lock:{run_id}")
    except Exception:
        pass


def _finish(
    run_id: str,
    status: str,
    payload: dict | None = None,
    error: str | None = None,
    refusal: dict | None = None,
    local_files: list[str] | None = None,
) -> None:
    """把终态写回 SieveRun（自己开 session，调用方不用管事务）。"""
    session = SessionLocal()
    try:
        run = session.query(SieveRun).filter(SieveRun.id == run_id).first()
        if run is None:
            return
        run.status = status
        if error is not None:
            run.error = error
        if payload:
            summary = payload.get("summary")
            if isinstance(summary, str):
                run.summary = summary
            elif summary is not None:
                # summary 可能是结构化对象，放 result 里，别塞进 Text 列
                run.result = summary
            if payload.get("result") is not None:
                run.result = payload["result"]
            if payload.get("files"):
                run.files = payload["files"]
            conformance = payload.get("schema_conformance") or {}
            if isinstance(conformance, dict) and conformance.get("status"):
                run.schema_conformance = conformance["status"]
            if payload.get("turns") is not None:
                try:
                    run.turns = int(payload["turns"])
                except (TypeError, ValueError):
                    pass
        if refusal:
            run.refusal_code = refusal.get("code")
        if local_files:
            run.local_files = local_files
        session.commit()
    finally:
        session.close()


def _create_and_poll(run_id: str) -> dict:
    """创建 run 并轮询到终态（真正的实现，供 celery 与测试直接调用）。"""
    session = SessionLocal()
    try:
        run = session.query(SieveRun).filter(SieveRun.id == run_id).first()
        if run is None:
            raise ValueError(f"sieve run 不存在: {run_id}")
        if run.status not in SieveRun.PENDING_STATUSES:
            logger.info(f"sieve run {run_id} 已是终态 {run.status}，跳过")
            return {"status": run.status, "run_id": run_id}

        client = SieveClient()
        try:
            payload = client.start_scrape(
                instruction=run.instruction,
                target_urls=run.target_urls,
                fields=run.fields,
                schema=run.schema,
                output_schema=run.output_schema,
                table_shape=run.table_shape,
                compliance_mode=run.compliance_mode,
            )
        except SieveAmbiguousRequest as e:
            # 可能已经创建成功（也确实可能扣了费）——不重试，交给人判断
            run.status = SieveRun.Status.AMBIGUOUS
            run.error = str(e)
            session.commit()
            logger.error(f"sieve run {run_id} 创建结果不明，未自动重试: {e}")
            return {"status": run.status, "run_id": run_id, "error": str(e)}
        except SieveNotConfigured:
            raise
        except SieveError as e:
            run.status = SieveRun.Status.ERROR
            run.error = str(e)
            session.commit()
            logger.error(f"sieve run {run_id} 创建失败: {e}")
            return {"status": run.status, "run_id": run_id, "error": str(e)}

        # ★ 先把 session_id 单独提交落库，再去轮询/下载：崩溃后能接着轮询而不是重开一次
        run.session_id = payload.get("session_id")
        run.status = SieveRun.Status.RUNNING
        run.error = None
        session.commit()
        logger.info(f"sieve run {run_id} 已创建: session_id={run.session_id}")
    finally:
        session.close()

    return _poll_run(run_id)


def _poll_run(run_id: str, expect_turns_after: int | None = None) -> dict:
    """轮询到终态并落库。返回 {status, run_id, ...}。"""
    session = SessionLocal()
    try:
        run = session.query(SieveRun).filter(SieveRun.id == run_id).first()
        if run is None:
            raise ValueError(f"sieve run 不存在: {run_id}")
        session_id = run.session_id
        if expect_turns_after is None and run.kind == SieveRun.Kind.FOLLOW_UP:
            expect_turns_after = run.baseline_turns
        if not session_id and run.kind == SieveRun.Kind.FOLLOW_UP and run.parent_id:
            # 追问用的是父 run 的远端会话（兜底：老行可能没把 session_id 抄过来）
            parent = session.query(SieveRun).filter(SieveRun.id == run.parent_id).first()
            session_id = parent.session_id if parent else None
    finally:
        session.close()

    if not session_id:
        logger.info(f"sieve run {run_id} 还没有 session_id，无需轮询（等待人工判断）")
        return {"status": "skipped", "run_id": run_id}

    if not _acquire_poll_lock(run_id):
        logger.info(f"sieve run {run_id} 已有轮询在跑，跳过本次")
        return {"status": "locked", "run_id": run_id}

    client = SieveClient()
    try:
        def _persist_status(payload: dict) -> None:
            """每次轮询都把远端状态写回本地——崩了也能从最近状态接着看。"""
            poll_session = SessionLocal()
            try:
                row = poll_session.query(SieveRun).filter(SieveRun.id == run_id).first()
                if row is None:
                    return
                if payload.get("status"):
                    row.status = SieveRun.Status.RUNNING
                if payload.get("turns") is not None:
                    try:
                        row.turns = int(payload["turns"])
                    except (TypeError, ValueError):
                        pass
                poll_session.commit()
            finally:
                poll_session.close()

        if expect_turns_after is None:
            payload = client.wait_for_run(
                session_id, max_wait=POLL_BUDGET_SECONDS, on_status=_persist_status
            )
        else:
            payload = client.wait_for_turn(
                session_id,
                previous_turns=expect_turns_after,
                max_wait=POLL_BUDGET_SECONDS,
                on_status=_persist_status,
            )
    except SieveTimeout as e:
        # run 还在跑，只是本次预算用完：状态留 running，交给补轮询任务接力
        logger.info(f"sieve run {run_id} 本轮预算用尽，保留 running 待接力: {e}")
        return {"status": "running", "run_id": run_id, "resumed": True}
    except SieveRefused as e:
        _finish(run_id, SieveRun.Status.REFUSED, error=str(e), refusal=e.refusal)
        logger.warning(f"sieve run {run_id} 被拒绝: code={e.code}")
        return {"status": "refused", "run_id": run_id, "refusal_code": e.code}
    except (SieveAuthError, SieveInsufficientCredits) as e:
        # 这两种要用户处理（换 key / 充值），记成 error 并保留原文供前端提示
        _finish(run_id, SieveRun.Status.ERROR, error=str(e))
        logger.error(f"sieve run {run_id} 需要用户处理: {e}")
        return {"status": "error", "run_id": run_id, "error": str(e)}
    except SieveError as e:
        _finish(run_id, SieveRun.Status.ERROR, error=str(e))
        logger.error(f"sieve run {run_id} 轮询失败: {e}")
        return {"status": "error", "run_id": run_id, "error": str(e)}
    finally:
        _release_poll_lock(run_id)

    saved_files = _save_files(run_id, payload)
    _finish(run_id, SieveRun.Status.DONE, payload=payload, local_files=saved_files)
    logger.info(
        f"sieve run {run_id} 完成: files={len(saved_files)} "
        f"conformance={(payload.get('schema_conformance') or {}).get('status')}"
    )
    return {"status": "done", "run_id": run_id, "files": saved_files}


def _save_files(run_id: str, payload: dict) -> list[str]:
    """把 files[] 逐个下到 data/sieve/<session_id>/。单个文件失败不影响其它文件。"""
    files = files_with_urls(payload.get("files"), settings.SIEVE_BASE_URL)
    if not files:
        return []
    client = SieveClient()
    out_dir = f"{settings.SIEVE_FILES_DIR}/{payload.get('session_id') or run_id}"
    saved: list[str] = []
    for f in files:
        name = str(f.get("name") or "artifact.bin")
        try:
            saved.append(client.download_file(f.get("url"), f"{out_dir}/{name}"))
        except SieveError as e:
            logger.error(f"sieve run {run_id} 交付文件下载失败 name={name}: {e}")
    return saved


@shared_task(bind=True, max_retries=0)
def run_sieve_scrape_task(self, run_id: str) -> dict:
    """创建 + 轮询的任务入口（不自动重试，理由见模块 docstring）。"""
    return _create_and_poll(run_id)


@shared_task(bind=True, max_retries=0)
def poll_sieve_run_task(self, run_id: str, expect_turns_after: int | None = None) -> dict:
    """纯轮询的任务入口（补轮询与追问接力都用它）。"""
    return _poll_run(run_id, expect_turns_after=expect_turns_after)


def _followup(run_id: str) -> dict:
    """追问：先记录 turn，再轮询到 done **且 turns 已推进**。

    `run_id` 指向本次追问新建的 `SieveRun`（kind=follow_up，parent_id 指向原始 run），
    行上的 `baseline_turns` 存的是**发起追问前的远端 turn 计数**。
    """
    session = SessionLocal()
    try:
        run = session.query(SieveRun).filter(SieveRun.id == run_id).first()
        if run is None:
            raise ValueError(f"sieve 追问记录不存在: {run_id}")
        parent = session.query(SieveRun).filter(SieveRun.id == run.parent_id).first()
        if parent is None or not parent.session_id:
            run.status = SieveRun.Status.ERROR
            run.error = "原始 run 还没有 session_id，无法追问"
            session.commit()
            return {"status": "error", "run_id": run_id, "error": run.error}
        baseline_turns = int(run.baseline_turns or 0)
        session_id = parent.session_id
        parent_id = str(parent.id)
        instruction = run.instruction
        # 追问跑在父 run 的同一个远端会话上：把 session_id 抄到本行，
        # 这样单看这一行就知道该轮询哪个会话（补轮询/详情页都不用再回查父行）
        run.session_id = session_id
        session.commit()
    finally:
        session.close()

    client = SieveClient()
    try:
        client.send_message(session_id, instruction=instruction)
    except SieveError as e:
        # 含 409（已有 turn 在飞）：没有创建任何东西，记下来让用户稍后重发
        _finish(run_id, SieveRun.Status.ERROR, error=f"{type(e).__name__}: {e}")
        logger.warning(f"sieve 追问被拒 ({run_id}): {e}")
        return {"status": "error", "run_id": run_id, "error": str(e)}

    result = _poll_run(run_id, expect_turns_after=baseline_turns)
    logger.info(f"sieve 追问 {run_id} 轮询结束: {result.get('status')}")
    return {**result, "parent_id": parent_id}


@shared_task(bind=True, max_retries=0)
def sieve_followup_task(self, run_id: str) -> dict:
    """追问任务的 Celery 入口。"""
    return _followup(run_id)


def _resume_pending() -> dict:
    """把 running 的 run 重新派给 worker。

    这就是"崩溃后恢复轮询而不是重开一次 run"的落点。POST 结果不明（ambiguous）的行
    **不会**被重派——没有 session_id 就没法确认，重派等于可能二次扣费。
    """
    session = SessionLocal()
    try:
        rows = (
            session.query(SieveRun)
            .filter(SieveRun.status.in_(list(SieveRun.PENDING_STATUSES)))
            .filter(SieveRun.session_id.isnot(None))
            .order_by(SieveRun.updated_at.asc())
            .limit(RESUME_BATCH_SIZE)
            .all()
        )
        pending = [(str(r.id), r.kind, r.baseline_turns) for r in rows]
    finally:
        session.close()

    dispatched = 0
    for run_id, kind, baseline_turns in pending:
        if kind == SieveRun.Kind.FOLLOW_UP and baseline_turns is not None:
            poll_sieve_run_task.delay(run_id, expect_turns_after=int(baseline_turns))
        else:
            poll_sieve_run_task.delay(run_id)
        dispatched += 1
    if dispatched:
        logger.info(f"sieve 补轮询派发 {dispatched} 个未完成 run")
    return {"dispatched": dispatched}


@shared_task(bind=True, max_retries=0)
def resume_pending_sieve_runs(self) -> dict:
    """beat 补轮询入口（每 5 分钟一次，见 celery_config.beat_schedule）。"""
    return _resume_pending()
