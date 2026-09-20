from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from app.config.database import get_db
from app.models.chapter import Chapter
from app.schemas.chapter import ChapterResponse, ChapterUpdate, ChapterListResponse, HumanizeRequest, ReviewAction

router = APIRouter(prefix="/projects/{project_id}/chapters", tags=["章节管理"])


@router.get("", response_model=ChapterListResponse)
async def list_chapters(project_id: UUID, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    total = db.query(Chapter).filter(Chapter.project_id == project_id).count()
    items = db.query(Chapter).filter(Chapter.project_id == project_id).order_by(Chapter.chapter_number).offset(skip).limit(limit).all()
    return ChapterListResponse(total=total, items=items)


@router.get("/humanize-status")
async def humanize_status(task_id: str, project_id: UUID, db: Session = Depends(get_db)):
    """查询去AI化任务状态 + 章节实际进度。
    返回 task_state (PENDING/STARTED/SUCCESS/FAILURE) + 章节级统计。
    前端用这个端点判断任务是否真的在跑，避免 worker 崩溃后前端干等。
    """
    from app.config.celery_config import celery_app
    # 章节级实际进度（从数据库统计，最准确）
    chapters = db.query(Chapter).filter(Chapter.project_id == project_id).all()
    total = len(chapters)
    completed = sum(1 for c in chapters if c.ai_score_after is not None)
    has_before = sum(1 for c in chapters if c.ai_score_before is not None)
    # 防御：task_id 为空时返回进度但不查 Celery（避免 ValueError）
    if not task_id:
        return {
            "task_id": "",
            "task_state": "UNKNOWN",
            "task_ready": False,
            "total_chapters": total,
            "completed": completed,
            "has_score_before": has_before,
            "progress_pct": round(completed / total * 100) if total > 0 else 0,
            "task_result": None,
        }
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "task_state": result.state,  # PENDING / STARTED / SUCCESS / FAILURE / RETRY
        "task_ready": result.ready(),
        "total_chapters": total,
        "completed": completed,
        "has_score_before": has_before,
        "progress_pct": round(completed / total * 100) if total > 0 else 0,
        "task_result": str(result.result) if result.ready() else None,
    }


@router.get("/{chapter_number}", response_model=ChapterResponse)
async def get_chapter(project_id: UUID, chapter_number: int, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id, Chapter.chapter_number == chapter_number
    ).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    return chapter


@router.put("/{chapter_number}", response_model=ChapterResponse)
async def update_chapter(project_id: UUID, chapter_number: int, data: ChapterUpdate, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id, Chapter.chapter_number == chapter_number
    ).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(chapter, key, value)
    db.commit()
    db.refresh(chapter)
    return chapter


@router.post("/{chapter_number}/humanize")
async def trigger_humanize(project_id: UUID, chapter_number: int, request: HumanizeRequest, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id, Chapter.chapter_number == chapter_number
    ).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    from app.tasks.novel_tasks import humanize_chapter
    humanize_chapter(str(chapter.id), request.strategy)
    db.refresh(chapter)
    return {
        "message": "去AI化完成",
        "chapter_id": str(chapter.id),
        "ai_score_before": chapter.ai_score_before,
        "ai_score_after": chapter.ai_score_after,
    }


@router.post("/humanize-all")
async def trigger_humanize_all(project_id: UUID, request: HumanizeRequest, db: Session = Depends(get_db)):
    """全局去 AI 化：批量处理项目下所有章节。
    优先 Celery 异步；Worker 不可用时降级为同步执行。
    支持断点续跑：已处理过的章节（有 ai_score_after）会自动跳过。
    """
    total = db.query(Chapter).filter(Chapter.project_id == project_id).count()
    if total == 0:
        raise HTTPException(status_code=400, detail="项目下没有章节可去AI化")
    from app.tasks.novel_tasks import humanize_project, clear_pause_flag
    clear_pause_flag(str(project_id))
    try:
        from app.config.celery_config import celery_app
        celery_app.connection().ensure_connection(max_retries=1)
        task = humanize_project.delay(str(project_id), request.strategy)
        return {
            "message": f"已提交全局去AI化任务（共{total}章）",
            "project_id": str(project_id),
            "total_chapters": total,
            "task_id": task.id,
            "mode": "async",
            "task_status_endpoint": f"/api/v1/projects/{project_id}/chapters/humanize-status?task_id={task.id}",
        }
    except Exception:
        import asyncio
        await asyncio.to_thread(humanize_project, str(project_id), request.strategy)
        completed = db.query(Chapter).filter(Chapter.project_id == project_id, Chapter.ai_score_after != None).count()
        return {
            "message": f"去AI化完成（同步模式，共{total}章，已完成{completed}章）",
            "project_id": str(project_id),
            "total_chapters": total,
            "completed": completed,
            "mode": "sync",
        }


@router.post("/humanize-pause")
async def humanize_pause(project_id: UUID, task_id: str = None, db: Session = Depends(get_db)):
    """暂停去AI化任务：保留当前进度，下次启动从断点继续。
    设置 Redis 暂停标志 + revoke 当前任务（不清理队列中已 ack 的）。
    """
    from app.tasks.novel_tasks import set_pause_flag
    from app.config.celery_config import celery_app
    set_pause_flag(str(project_id))
    if task_id:
        celery_app.control.revoke(task_id, terminate=False, signal="SIGUSR1")
    return {"message": "已发送暂停信号，当前章节处理完后会停止，下次启动从断点继续", "project_id": str(project_id)}


@router.post("/humanize-stop")
async def humanize_stop(project_id: UUID, task_id: str = None, db: Session = Depends(get_db)):
    """停止去AI化任务：清除所有进度，下次启动从头开始。
    revoke 任务 + 重置所有章节的 ai_score_before/after + 恢复原文。
    """
    from app.tasks.novel_tasks import reset_humanize_progress, clear_pause_flag
    from app.config.celery_config import celery_app
    if task_id:
        # v1.5.0：Windows 没有 SIGKILL，用 SIGTERM 兼容所有平台
        import sys
        sig = "SIGTERM" if sys.platform == "win32" else "SIGKILL"
        celery_app.control.revoke(task_id, terminate=True, signal=sig)
    clear_pause_flag(str(project_id))
    reset_humanize_progress(str(project_id))
    return {"message": "已停止去AI化并重置所有进度，下次启动从头开始", "project_id": str(project_id)}


@router.post("/{chapter_number}/approve", response_model=ChapterResponse)
async def approve_chapter(project_id: UUID, chapter_number: int, action: ReviewAction = None, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id, Chapter.chapter_number == chapter_number
    ).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    chapter.review_status = "approved"
    if action and action.comment:
        chapter.review_comment = action.comment
    db.commit()
    # 项目状态自动流转：所有章节都 approved → project.status = "reviewed"
    from app.models.project import Project
    project = db.query(Project).filter(Project.id == project_id).first()
    if project and project.status == "pending_review":
        all_chapters = db.query(Chapter).filter(Chapter.project_id == project_id).all()
        if all_chapters and all(c.review_status == "approved" for c in all_chapters):
            project.status = "reviewed"
            db.commit()
            import logging
            logging.getLogger(__name__).info(f"项目全部章节审核通过，状态流转: pending_review -> reviewed, project={project_id}")
    db.refresh(chapter)
    return chapter


@router.post("/{chapter_number}/reject", response_model=ChapterResponse)
async def reject_chapter(project_id: UUID, chapter_number: int, action: ReviewAction, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id, Chapter.chapter_number == chapter_number
    ).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    chapter.review_status = "rejected"
    if action.comment:
        chapter.review_comment = action.comment
    db.commit()
    # 有章节被拒绝 → 项目回退到 pending_review（如果之前是 reviewed）
    from app.models.project import Project
    project = db.query(Project).filter(Project.id == project_id).first()
    if project and project.status == "reviewed":
        project.status = "pending_review"
        db.commit()
        import logging
        logging.getLogger(__name__).info(f"章节{chapter_number}被拒绝，项目状态回退: reviewed -> pending_review, project={project_id}")
    db.refresh(chapter)
    return chapter