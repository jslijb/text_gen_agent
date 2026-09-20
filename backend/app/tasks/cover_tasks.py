"""封面生成 Celery 任务（spec v1.4.0 规则 9）

创建项目时自动投递此任务，异步生成封面。
失败不阻塞项目创建，仅记录日志。
"""
import logging
from celery import shared_task
from app.config.database import SessionLocal
from app.models.project import Project

logger = logging.getLogger(__name__)


@shared_task
def generate_cover_task(project_id: str):
    """异步生成封面任务（spec v1.4.0 规则 9）

    查询项目信息 → 调用 cover_service.generate_cover → 更新 cover_url
    失败仅记录日志，不抛异常（不阻塞项目创建）。
    """
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error(f"封面任务失败：项目不存在 {project_id}")
            return

        logger.info(f"自动生成封面开始: project={project_id}, name={project.name}")

        from app.services.cover_service import generate_cover, CoverGenerationError
        try:
            result = generate_cover(
                project_id=project_id,
                gender=project.gender,
                genre=project.genre,
                name=project.name,
                synopsis=project.synopsis,
            )
            project.cover_url = result["cover_url"]
            db.commit()
            logger.info(f"自动生成封面完成: project={project_id}, cover_url={result['cover_url']}")

            # 通过 WebSocket 推送封面更新事件
            try:
                from app.api.ws import broadcast_progress
                broadcast_progress(project_id, {
                    "type": "cover_generated",
                    "project_id": project_id,
                    "cover_url": result["cover_url"],
                })
            except Exception as ws_err:
                logger.debug(f"WebSocket 推送封面更新失败（不影响主流程）: {ws_err}")

        except CoverGenerationError as e:
            # 封面生成失败不阻塞项目创建，仅记录日志
            logger.error(f"自动生成封面失败: project={project_id}, error={e}", exc_info=True)
        except Exception as e:
            logger.error(f"自动生成封面未知异常: project={project_id}, error={e}", exc_info=True)

    except Exception as e:
        logger.error(f"封面任务执行异常: {e}", exc_info=True)
    finally:
        db.close()
