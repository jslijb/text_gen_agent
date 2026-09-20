"""封面生成 API 端点（spec 5.8 / design 2.2 封面生成）"""
import logging
import os
import time

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import settings
from app.models.project import Project
from app.schemas.cover import CoverGenerateRequest, CoverGenerateResponse, CoverResponse
from app.services import cover_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["封面生成"])


@router.post(
    "/projects/{project_id}/cover/generate",
    response_model=CoverGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="生成封面",
)
def generate_cover(
    project_id: str,
    req: CoverGenerateRequest,
    db: Session = Depends(get_db),
):
    """生成封面（Agnes LLM 编排 + Agnes 图像 API 文生图，spec 5.8.1 规则 4 v1.4.0）"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        result = cover_service.generate_cover(
            project_id=str(project.id),
            gender=req.gender,
            genre=req.genre,
            name=project.name,
            synopsis=project.synopsis,
        )
    except cover_service.CoverGenerationError as e:
        # spec 5.8.3 异常场景 1：Agnes 图像 API 不可达
        logger.error(f"封面生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="封面生成服务暂时不可用，请稍后重试")
    except Exception as e:
        # spec 5.8.3 异常场景 3：封面图片保存失败
        logger.error(f"封面生成内部错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="封面保存失败，请联系管理员")

    # 更新 Project.cover_url
    project.cover_url = result["cover_url"]
    db.commit()
    logger.info(f"项目 {project_id} 封面已更新: {result['cover_url']}")

    return CoverGenerateResponse(
        cover_url=result["cover_url"],
        prompt_used=result["prompt_used"],
        model_used=result["model_used"],
    )


@router.get(
    "/projects/{project_id}/cover",
    response_model=CoverResponse,
    summary="获取封面 URL",
)
def get_cover(project_id: str, db: Session = Depends(get_db)):
    """获取项目封面 URL（spec 5.8.1 规则 6）"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return CoverResponse(cover_url=project.cover_url)


@router.post(
    "/projects/{project_id}/cover/upload",
    response_model=CoverResponse,
    summary="上传封面图片",
)
async def upload_cover(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传自定义封面图片，替换 AI 生成的封面"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 校验文件类型
    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
    content_type = file.content_type or ""
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"不支持的图片格式: {content_type}，仅支持 PNG/JPEG/WebP/GIF")

    # 校验文件大小（10MB）
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 10MB")

    # 根据类型确定扩展名
    ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
    ext = ext_map.get(content_type, ".png")

    # 确保目录存在
    os.makedirs(settings.COVERS_DIR, exist_ok=True)

    # 保存文件
    filename = f"{project_id}_{int(time.time())}{ext}"
    filepath = os.path.join(settings.COVERS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    cover_url = f"/static/covers/{filename}"
    project.cover_url = cover_url
    db.commit()

    logger.info(f"项目 {project_id} 封面已上传: {cover_url} ({len(content)} bytes)")
    return CoverResponse(cover_url=cover_url)
