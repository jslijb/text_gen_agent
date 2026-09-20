import logging
from datetime import datetime, timedelta, timezone
from celery import shared_task
from app.config.database import SessionLocal
from app.models.chapter import Chapter
from app.models.project import Project
from app.models.config import PublishQueue
from app.api.ws import broadcast_publish_status
from app.config import platforms as pf

logger = logging.getLogger(__name__)

# 2026-09-15：日更时间判定必须用北京时间。
# 容器默认时区是 UTC，datetime.now() 会比北京时间差 8 小时，
# 会让 daily_publish_time=08:00 的实际触发点漂到下午 16:00。
CST = timezone(timedelta(hours=8))

# 当日去重键：TTL 给足 36 小时，跨天自动失效，无需人工清理
DAILY_RUN_KEY = "daily:ran:{}:{}"
DAILY_RUN_TTL = 36 * 3600


def _mark_daily_run_once(project_id: str, day: str) -> bool:
    """当天首次调用返回 True，重复调用返回 False。

    Redis 不可用时按放行处理 —— 宁可重复跑一次（续写任务自带互斥锁），
    也不要因为基础设施抖动让日更彻底停摆。
    """
    try:
        from app.config.celery_config import celery_app
        import redis as redis_lib
        broker = celery_app.conf.broker_url.replace("redis://", "").split("/")[0]
        r = redis_lib.Redis.from_url(f"redis://{broker}/1")
        return bool(r.set(DAILY_RUN_KEY.format(project_id, day), "1", nx=True, ex=DAILY_RUN_TTL))
    except Exception as e:
        logger.warning(f"日更去重标记失败，按放行处理: {e}")
        return True


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def publish_chapter_task(self, chapter_id: str):
    db = SessionLocal()
    try:
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            logger.error(f"章节不存在: {chapter_id}")
            return
        if chapter.review_status != "approved":
            logger.warning(f"章节未审核通过，跳过发布: {chapter_id}")
            return

        # 平台不支持自动发布时直接返回，别把番茄的稿子送进百度发布流程。
        # 必须放在"置 publishing"之前，否则会把 publish_status 永久留在 publishing。
        project = db.query(Project).filter(Project.id == chapter.project_id).first()
        if project and not pf.supports_auto_publish(project.platform):
            logger.warning(
                f"平台={project.platform} 不支持自动发布，跳过章节 {chapter.chapter_number} "
                f"（{chapter_id}），请手动导出投稿"
            )
            return

        chapter.publish_status = "publishing"
        db.commit()
        broadcast_publish_status(str(chapter.project_id), {"type": "status", "chapter": chapter.chapter_number, "status": "publishing", "message": f"正在发布第{chapter.chapter_number}章"})

        project_name = project.name if project else "未命名"
        is_first = chapter.chapter_number == 1

        from app.services.publisher import Publisher
        publisher = Publisher()
        result = publisher.publish_chapter(
            project_name=project_name,
            chapter_title=chapter.title,
            chapter_content=chapter.content,
            is_first=is_first,
            synopsis=project.synopsis if project else "",
            genre=project.genre if project else "",
        )

        if result["success"]:
            chapter.publish_status = "under_review"
            broadcast_publish_status(str(chapter.project_id), {"type": "status", "chapter": chapter.chapter_number, "status": "under_review", "message": f"第{chapter.chapter_number}章已提交，审核中"})
            logger.info(f"章节发布成功: {chapter_id}")
        else:
            chapter.publish_status = "unpublished"
            queue_item = PublishQueue(
                chapter_id=chapter.id,
                retry_count=self.request.retries,
                last_error=result.get("error", ""),
                status="failed" if self.request.retries >= 2 else "pending",
            )
            db.add(queue_item)
            broadcast_publish_status(str(chapter.project_id), {"type": "error", "chapter": chapter.chapter_number, "message": result.get("error", "发布失败")})
            raise Exception(result.get("error", "发布失败"))

        db.commit()
    except Exception as e:
        logger.error(f"发布失败: {e}", exc_info=True)
        db.rollback()
        raise self.retry(exc=e)
    finally:
        db.close()


@shared_task
def login_baidu_task(timeout_seconds: int = 300):
    """Celery 任务：打开浏览器让用户手动登录百度作家平台。
    替代原 publisher.open_login_browser 的线程方式（线程方式在 API 返回后会被回收）。
    """
    from app.services.publisher import Publisher
    publisher = Publisher()
    try:
        result = publisher.open_login_browser(timeout_seconds=timeout_seconds)
        logger.info(f"百度登录任务完成: {result}")
        return result
    except Exception as e:
        logger.error(f"百度登录任务失败: {e}", exc_info=True)
        return {"success": False, "message": f"登录失败: {e}", "cookie_count": 0}


@shared_task
def check_and_publish_scheduled():
    """
    日更调度：每小时检查，到达 daily_publish_time 时：
    1. 如果项目还有未生成的章节（章节数 < total_chapters），先续写新章节
    2. 然后发布已审核通过的未发布章节
    """
    db = SessionLocal()
    try:
        now = datetime.now(CST)
        current_hhmm = now.strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")
        projects = db.query(Project).filter(
            Project.status.in_(["reviewed", "pending_review"])
        ).all()
        triggered = 0
        for project in projects:
            target_hhmm = (project.daily_publish_time or "08:00")[:5]
            # 2026-09-15 修复：原判定是"当前 HH:MM 与配置精确相等"，
            # 但 beat 是按间隔触发的、相位由进程启动时刻决定（实测落在 21:55 / 22:54），
            # 于是 daily_publish_time=08:00 几乎永远撞不上 —— 日更一次都没触发过。
            # 现改为"到点或已过点，且当天还没跑过"：
            # HH:MM 补零后字典序即时间序，字符串比较可直接当时间比较用。
            if current_hhmm < target_hhmm:
                continue  # 还没到点
            if not _mark_daily_run_once(str(project.id), today):
                continue  # 当天已经跑过，避免 beat 高频检查导致一天续写多次
            existing_count = db.query(Chapter).filter(
                Chapter.project_id == project.id
            ).count()
            total_target = project.total_chapters or 30
            # 步骤1：如果还有未生成的章节，触发续写
            if existing_count < total_target:
                from app.tasks.novel_tasks import generate_daily_chapters
                generate_daily_chapters.delay(str(project.id))
                logger.info(f"项目[{project.name}]触发日更续写：已有{existing_count}章，目标{total_target}章")
            # 步骤2：发布已审核通过的未发布章节
            # 2026-09-15：先按平台拦截。番茄的自动发布尚未实现（publish_host=None），
            # 不拦的话会把番茄章节丢进百度发布器（zuojia.baidu.com 的 Playwright 流程），
            # 每次必然失败并产生 3 次重试 + PublishQueue 失败记录。
            if not pf.supports_auto_publish(project.platform):
                logger.info(
                    f"项目[{project.name}]平台={project.platform} 暂不支持自动发布，跳过发布步骤"
                )
                continue
            pending_chapters = db.query(Chapter).filter(
                Chapter.project_id == project.id,
                Chapter.review_status == "approved",
                Chapter.publish_status == "unpublished",
            ).order_by(Chapter.chapter_number.asc()).limit(project.daily_chapters or 2).all()
            for ch in pending_chapters:
                publish_chapter_task.delay(str(ch.id))
                triggered += 1
            if pending_chapters:
                logger.info(f"项目[{project.name}]触发日更发布{len(pending_chapters)}章")
        if triggered:
            logger.info(f"日更调度检查完成，共触发{triggered}章发布")
    except Exception as e:
        logger.error(f"日更调度检查失败: {e}", exc_info=True)
    finally:
        db.close()