from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, List

from app.config.database import get_db
from app.models.video import VideoProject, VideoShot, VideoAsset
from app.schemas.ai_video import (
    VideoProject, VideoProjectCreate, VideoProjectUpdate, VideoProjectResponse,
    VideoProjectListResponse, Shot, ShotCreate, ShotUpdate, ShotResponse,
    ShotListResponse, Asset, AssetCreate, AssetResponse, AssetListResponse,
    TaskResponse, TaskStatusResponse, VideoProjectStatus, VideoShotStatus
)

router = APIRouter(prefix="/video", tags=["视频生成"])


# ============ 项目管理 ============

@router.post("/projects", response_model=VideoProjectResponse, status_code=201)
async def create_project(data: VideoProjectCreate, db: Session = Depends(get_db)):
    """创建视频项目"""
    project = VideoProject(**data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return VideoProjectResponse(project=project)


@router.get("/projects", response_model=VideoProjectListResponse)
async def list_projects(
    skip: int = 0, 
    limit: int = 20, 
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取视频项目列表"""
    query = db.query(VideoProject)
    if status:
        query = query.filter(VideoProject.status == status)
    total = query.count()
    items = query.order_by(VideoProject.created_at.desc()).offset(skip).limit(limit).all()
    return VideoProjectListResponse(projects=items, total=total)


@router.get("/projects/{project_id}", response_model=VideoProjectResponse)
async def get_project(project_id: UUID, db: Session = Depends(get_db)):
    """获取视频项目详情"""
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return VideoProjectResponse(project=project)


@router.put("/projects/{project_id}", response_model=VideoProjectResponse)
async def update_project(
    project_id: UUID, 
    data: VideoProjectUpdate, 
    db: Session = Depends(get_db)
):
    """更新视频项目"""
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    
    db.commit()
    db.refresh(project)
    return VideoProjectResponse(project=project)


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: UUID, db: Session = Depends(get_db)):
    """删除视频项目"""
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    db.delete(project)
    db.commit()
    return {"message": "删除成功"}


# ============ 分镜管理 ============

@router.post("/projects/{project_id}/shots", response_model=ShotResponse, status_code=201)
async def create_shot(
    project_id: UUID, 
    data: ShotCreate, 
    db: Session = Depends(get_db)
):
    """创建分镜"""
    # 验证项目存在
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    shot = VideoShot(**data.model_dump())
    db.add(shot)
    db.commit()
    db.refresh(shot)
    return ShotResponse(shot=shot)


@router.get("/projects/{project_id}/shots", response_model=ShotListResponse)
async def list_shots(
    project_id: UUID, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """获取分镜列表"""
    total = db.query(VideoShot).filter(VideoShot.project_id == project_id).count()
    items = db.query(VideoShot).filter(VideoShot.project_id == project_id).order_by(VideoShot.sequence).offset(skip).limit(limit).all()
    return ShotListResponse(shots=items, total=total)


@router.get("/projects/{project_id}/shots/{shot_id}", response_model=ShotResponse)
async def get_shot(project_id: UUID, shot_id: UUID, db: Session = Depends(get_db)):
    """获取分镜详情"""
    shot = db.query(VideoShot).filter(VideoShot.id == shot_id, VideoShot.project_id == project_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")
    return ShotResponse(shot=shot)


@router.put("/projects/{project_id}/shots/{shot_id}", response_model=ShotResponse)
async def update_shot(
    project_id: UUID, 
    shot_id: UUID, 
    data: ShotUpdate, 
    db: Session = Depends(get_db)
):
    """更新分镜"""
    shot = db.query(VideoShot).filter(VideoShot.id == shot_id, VideoShot.project_id == project_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(shot, key, value)
    
    db.commit()
    db.refresh(shot)
    return ShotResponse(shot=shot)


@router.delete("/projects/{project_id}/shots/{shot_id}", status_code=204)
async def delete_shot(project_id: UUID, shot_id: UUID, db: Session = Depends(get_db)):
    """删除分镜"""
    shot = db.query(VideoShot).filter(VideoShot.id == shot_id, VideoShot.project_id == project_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="分镜不存在")
    
    db.delete(shot)
    db.commit()
    return {"message": "删除成功"}


# ============ 素材管理 ============

@router.get("/assets", response_model=AssetListResponse)
async def list_assets(
    skip: int = 0, 
    limit: int = 20, 
    asset_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取素材列表"""
    query = db.query(VideoAsset)
    if asset_type:
        query = query.filter(VideoAsset.type == asset_type)
    total = query.count()
    items = query.order_by(VideoAsset.created_at.desc()).offset(skip).limit(limit).all()
    return AssetListResponse(assets=items, total=total)


@router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: UUID, db: Session = Depends(get_db)):
    """获取素材详情"""
    asset = db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="素材不存在")
    return AssetResponse(asset=asset)


# ============ 视频生成任务 ============

@router.post("/projects/{project_id}/generate-topic", response_model=TaskResponse)
async def generate_topic(project_id: UUID):
    """生成选题"""
    # TODO: 提交Celery任务
    from app.tasks.video_tasks import generate_topic_task
    task = generate_topic_task.delay(str(project_id))
    return TaskResponse(task_id=task.id, status="processing")


@router.post("/projects/{project_id}/generate-script", response_model=TaskResponse)
async def generate_script(project_id: UUID):
    """生成文案"""
    # TODO: 提交Celery任务
    from app.tasks.video_tasks import generate_script_task
    task = generate_script_task.delay(str(project_id))
    return TaskResponse(task_id=task.id, status="processing")


@router.post("/projects/{project_id}/generate-shots", response_model=TaskResponse)
async def generate_shots(project_id: UUID):
    """生成分镜"""
    # TODO: 提交Celery任务
    from app.tasks.video_tasks import generate_shots_task
    task = generate_shots_task.delay(str(project_id))
    return TaskResponse(task_id=task.id, status="processing")


@router.post("/projects/{project_id}/generate-assets", response_model=TaskResponse)
async def generate_assets(project_id: UUID):
    """生成素材"""
    # TODO: 提交Celery任务
    from app.tasks.video_tasks import generate_assets_task
    task = generate_assets_task.delay(str(project_id))
    return TaskResponse(task_id=task.id, status="processing")


@router.post("/projects/{project_id}/generate-video", response_model=TaskResponse)
async def generate_video(project_id: UUID):
    """生成视频"""
    # TODO: 提交Celery任务
    from app.tasks.video_tasks import generate_video_task
    task = generate_video_task.delay(str(project_id))
    return TaskResponse(task_id=task.id, status="processing")


@router.post("/projects/{project_id}/full-pipeline", response_model=TaskResponse)
async def full_pipeline(project_id: UUID):
    """完整生成流程"""
    # TODO: 提交Celery任务
    from app.tasks.video_tasks import full_pipeline_task
    task = full_pipeline_task.delay(str(project_id))
    return TaskResponse(task_id=task.id, status="processing")


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """获取任务状态"""
    # TODO: 查询Celery任务状态
    from celery.result import AsyncResult
    result = AsyncResult(task_id)
    
    status_map = {
        "PENDING": "pending",
        "STARTED": "processing",
        "SUCCESS": "completed",
        "FAILURE": "failed"
    }
    
    return TaskStatusResponse(
        task_id=task_id,
        status=status_map.get(result.state, result.state),
        progress=result.result.get("progress") if isinstance(result.result, dict) else None,
        current_step=result.result.get("current_step") if isinstance(result.result, dict) else None,
        result=result.result if result.state == "SUCCESS" else None,
        error=str(result.result) if result.state == "FAILURE" else None
    )