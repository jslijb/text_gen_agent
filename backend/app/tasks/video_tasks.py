"""
AI漫剧/视频生成Celery任务

包含视频生成相关的异步任务:
- 选题生成任务
- 文案生成任务
- 分镜生成任务
- 素材生成任务
- 视频生成任务
- 完整流程任务
"""

import logging
from celery import shared_task
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.video import VideoProject, VideoShot
from app.services.ai_video_engine import VideoEngineService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_topic_task(self, project_id: str):
    """选题生成任务"""
    try:
        db: Session = next(get_db())
        
        # 更新项目状态
        project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")
        
        project.status = VideoProject.Status.GENERATING
        db.commit()
        
        # 生成选题
        engine = VideoEngineService()
        topic = engine.topic_generator.generate(project_id)
        
        # 更新项目
        project.topic = topic.get("title", "")
        project.config = {"topic": topic}
        db.commit()
        
        logger.info(f"选题生成完成: project_id={project_id}, topic={topic}")
        
        return {
            "status": "completed",
            "project_id": project_id,
            "topic": topic
        }
    except Exception as e:
        logger.error(f"选题生成失败: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_script_task(self, project_id: str):
    """文案生成任务"""
    try:
        db: Session = next(get_db())
        
        project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")
        
        # 从配置中获取选题
        topic = project.config.get("topic", {}) if project.config else {}
        
        # 生成文案
        engine = VideoEngineService()
        script = engine.script_writer.generate(project_id, topic)
        
        # 更新项目
        if project.config:
            project.config["script"] = script
        else:
            project.config = {"script": script}
        db.commit()
        
        logger.info(f"文案生成完成: project_id={project_id}, title={script.get('title')}")
        
        return {
            "status": "completed",
            "project_id": project_id,
            "script": script
        }
    except Exception as e:
        logger.error(f"文案生成失败: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_shots_task(self, project_id: str):
    """分镜生成任务"""
    try:
        db: Session = next(get_db())
        
        project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")
        
        # 从配置中获取文案
        script = project.config.get("script", {}) if project.config else {}
        
        # 生成分镜
        engine = VideoEngineService()
        shots = engine.shot_splitter.split(project_id, script)
        
        # 保存分镜到数据库
        for i, shot_data in enumerate(shots):
            shot = VideoShot(
                project_id=project_id,
                sequence=i + 1,
                description=shot_data.get("description", ""),
                narration=shot_data.get("narration", ""),
                duration=shot_data.get("duration", 5),
                image_prompt=shot_data.get("image_prompt", ""),
                video_prompt=shot_data.get("video_prompt", ""),
                status=VideoShot.Status.PENDING
            )
            db.add(shot)
        
        db.commit()
        
        logger.info(f"分镜生成完成: project_id={project_id}, shots={len(shots)}")
        
        return {
            "status": "completed",
            "project_id": project_id,
            "shots_count": len(shots)
        }
    except Exception as e:
        logger.error(f"分镜生成失败: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_assets_task(self, project_id: str):
    """素材生成任务"""
    try:
        db: Session = next(get_db())
        
        project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")
        
        # 获取分镜
        shots = db.query(VideoShot).filter(VideoShot.project_id == project_id).order_by(VideoShot.sequence).all()
        
        # 生成素材
        engine = VideoEngineService()
        shot_data = [{
            "id": str(shot.id),
            "description": shot.description,
            "image_prompt": shot.image_prompt
        } for shot in shots]
        
        assets = await engine.asset_generator.generate(project_id, shot_data)
        
        # 保存素材到数据库
        for asset_data in assets:
            asset = VideoAsset(
                type=asset_data.get("type", "character"),
                name=asset_data.get("name", ""),
                image_url=asset_data.get("image_url", ""),
                metadata=asset_data
            )
            db.add(asset)
        
        db.commit()
        
        logger.info(f"素材生成完成: project_id={project_id}, assets={len(assets)}")
        
        return {
            "status": "completed",
            "project_id": project_id,
            "assets_count": len(assets)
        }
    except Exception as e:
        logger.error(f"素材生成失败: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def generate_video_task(self, project_id: str):
    """视频生成任务"""
    try:
        db: Session = next(get_db())
        
        project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")
        
        # 获取分镜和素材
        shots = db.query(VideoShot).filter(VideoShot.project_id == project_id).order_by(VideoShot.sequence).all()
        assets = db.query(VideoAsset).all()
        
        # 生成视频
        engine = VideoEngineService()
        shot_data = [{
            "id": str(shot.id),
            "description": shot.description,
            "image_prompt": shot.image_prompt,
            "video_prompt": shot.video_prompt,
            "duration": shot.duration
        } for shot in shots]
        
        asset_data = [{
            "id": str(asset.id),
            "type": asset.type,
            "image_url": asset.image_url
        } for asset in assets]
        
        video_url = await engine.video_generator.generate(project_id, shot_data, asset_data)
        
        # 更新项目
        project.status = VideoProject.Status.COMPLETED
        project.completed_at = datetime.utcnow()
        if project.config:
            project.config["video_url"] = video_url
        else:
            project.config = {"video_url": video_url}
        db.commit()
        
        logger.info(f"视频生成完成: project_id={project_id}, video_url={video_url}")
        
        return {
            "status": "completed",
            "project_id": project_id,
            "video_url": video_url
        }
    except Exception as e:
        logger.error(f"视频生成失败: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def full_pipeline_task(self, project_id: str):
    """完整流程任务"""
    try:
        db: Session = next(get_db())
        
        project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")
        
        # 更新状态
        project.status = VideoProject.Status.GENERATING
        db.commit()
        
        # 执行完整流程
        engine = VideoEngineService()
        result = await engine.full_pipeline(project_id)
        
        # 更新项目状态
        project.status = VideoProject.Status.COMPLETED
        project.completed_at = datetime.utcnow()
        project.config = result
        db.commit()
        
        logger.info(f"完整流程完成: project_id={project_id}")
        
        return {
            "status": "completed",
            "project_id": project_id,
            "result": result
        }
    except Exception as e:
        logger.error(f"完整流程失败: {e}", exc_info=True)
        
        # 更新项目状态为失败
        try:
            db: Session = next(get_db())
            project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
            if project:
                project.status = VideoProject.Status.FAILED
                db.commit()
        except:
            pass
        
        raise self.retry(exc=e)