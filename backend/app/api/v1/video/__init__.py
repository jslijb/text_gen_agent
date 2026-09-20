from fastapi import APIRouter
from app.api.v1.video.projects import router as video_router

api_router = APIRouter(prefix="/v1")

# 注册视频生成API路由
api_router.include_router(video_router, prefix="/video", tags=["视频生成"])