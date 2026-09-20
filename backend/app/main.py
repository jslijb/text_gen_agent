from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config.settings import settings
from app.config.database import engine, Base
from app.config.logging_config import setup_logging
from app.api import projects, chapters, knowledge, publish, config_api, ws, hot_topics, covers
from app.api.v1.video import api_router as video_api_router
import os
import logging

# 初始化文件日志系统（用户规则6）
setup_logging()
logger = logging.getLogger(__name__)

# 确保 API 进程也初始化 celery_app，使 shared_task 能正确绑定 broker 配置
from app.config.celery_config import celery_app  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    os.makedirs(settings.NOVELS_DIR, exist_ok=True)
    os.makedirs(settings.COOKIES_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    # spec 5.8.1 规则5：创建封面存储目录
    os.makedirs(settings.STATIC_DIR, exist_ok=True)
    os.makedirs(settings.COVERS_DIR, exist_ok=True)
    os.makedirs(settings.VIDEOS_DIR, exist_ok=True)
    os.makedirs(settings.BGM_DIR, exist_ok=True)
    # 启动模型配置热加载监听（spec 5.5.1 规则 4 / design 1.3.6）
    from app.services.config_service import ConfigService
    ConfigService.start_watching()
    logger.info("配置热加载已启动")
    yield
    # 关闭热加载监听
    ConfigService.stop_watching()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix=settings.API_PREFIX)
app.include_router(chapters.router, prefix=settings.API_PREFIX)
app.include_router(knowledge.router, prefix=settings.API_PREFIX)
app.include_router(publish.router, prefix=settings.API_PREFIX)
app.include_router(config_api.router, prefix=settings.API_PREFIX)
app.include_router(hot_topics.router, prefix=settings.API_PREFIX)
app.include_router(covers.router, prefix=settings.API_PREFIX)
app.include_router(ws.router)
app.include_router(video_api_router, prefix=settings.API_PREFIX)

# spec 5.8.1 规则5：挂载静态文件目录，提供封面图片访问
# StaticFiles 要求目录在挂载时存在，这里先创建再挂载
os.makedirs(settings.STATIC_DIR, exist_ok=True)
os.makedirs(settings.COVERS_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}