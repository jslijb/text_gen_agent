import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.config.database import get_db
from app.config.settings import settings
from app.models.chapter import Chapter
from app.models.project import Project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/publish", tags=["发布管理"])


@router.post("/project/{project_id}", status_code=202)
async def publish_project(project_id: UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    chapters = db.query(Chapter).filter(
        Chapter.project_id == project_id, Chapter.review_status == "approved"
    ).all()
    if not chapters:
        raise HTTPException(status_code=400, detail="没有已审核通过的章节可发布")
    from app.tasks.publish_tasks import publish_chapter_task
    for chapter in chapters:
        if chapter.publish_status == "unpublished":
            publish_chapter_task.delay(str(chapter.id))
    return {"message": f"已提交{len(chapters)}章发布任务"}


@router.post("/chapter/{chapter_id}", status_code=202)
async def publish_chapter(chapter_id: UUID, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    if chapter.review_status != "approved":
        raise HTTPException(status_code=400, detail="章节未审核通过，无法发布")
    from app.tasks.publish_tasks import publish_chapter_task
    publish_chapter_task.delay(str(chapter_id))
    return {"message": "发布任务已提交", "chapter_id": str(chapter_id)}


@router.get("/status/{chapter_id}")
async def publish_status(chapter_id: UUID, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    return {"chapter_id": str(chapter.id), "publish_status": chapter.publish_status}


# ---------- 登录状态文件辅助 ----------
def _login_status_path() -> Path:
    return Path(settings.COOKIES_DIR) / ".login_status.json"


def _write_login_status(status: str, message: str, cookie_count: int = 0):
    p = _login_status_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "status": status,  # pending / success / failed
        "message": message,
        "cookie_count": cookie_count,
        "updated_at": datetime.now().isoformat(),
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.post("/login", status_code=202)
async def login_baidu():
    """启动独立子进程打开浏览器登录百度作家平台。

    不走 Celery worker：Playwright 在 Celery worker 子进程中报 NotImplementedError
    （Windows ProactorEventLoop 在子进程中不支持 subprocess_exec），浏览器进程无法启动。
    独立子进程不受此限制，浏览器进程随子进程存活，登录完成后子进程退出。

    前端通过 GET /publish/login-status 轮询状态文件获取登录结果。
    """
    backend_dir = str(Path(__file__).resolve().parent.parent.parent)  # backend 目录
    _write_login_status("pending", "正在启动浏览器...")

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "app.services.login_runner", "--timeout", "300"],
            cwd=backend_dir,
            # 标准输出/错误独立，不阻塞 API
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            # Windows 下 CREATE_NEW_PROCESS_GROUP 避免被 Ctrl+C 影响
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        logger.info(f"已启动登录子进程 PID={proc.pid}, cwd={backend_dir}")
    except Exception as e:
        _write_login_status("failed", f"启动登录子进程失败: {e}")
        logger.error(f"启动登录子进程失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"启动登录失败: {e}")

    return {
        "message": "浏览器将在独立进程中打开，请在前台手动登录百度账号（5分钟超时）",
        "pid": proc.pid,
        "status_endpoint": "/api/v1/publish/login-status",
    }


@router.get("/login-status")
async def login_status():
    """查询登录状态。返回:
    - idle: 未发起登录
    - pending: 浏览器已打开，等待用户登录
    - success: 登录成功，Cookie 已保存
    - failed: 登录失败/超时
    """
    p = _login_status_path()
    if not p.exists():
        return {"status": "idle", "message": "未发起登录", "cookie_count": 0}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"状态读取失败: {e}", "cookie_count": 0}


@router.post("/login-cancel")
async def login_cancel():
    """取消登录（重置状态文件）"""
    p = _login_status_path()
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass
    return {"message": "登录状态已重置"}


@router.get("/cookie-status")
async def cookie_status():
    from app.services.publisher import Publisher
    publisher = Publisher()
    valid = publisher.check_cookie_valid()
    return {"cookie_valid": valid}
