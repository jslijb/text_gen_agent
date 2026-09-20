from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, channel: str, websocket: WebSocket):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket):
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
            if not self.active_connections[channel]:
                del self.active_connections[channel]

    async def broadcast(self, channel: str, message: dict):
        if channel in self.active_connections:
            data = json.dumps(message, ensure_ascii=False)
            for connection in self.active_connections[channel].copy():
                try:
                    await connection.send_text(data)
                except Exception:
                    self.active_connections[channel].discard(connection)


manager = ConnectionManager()


@router.websocket("/ws/progress/{project_id}")
async def progress_ws(websocket: WebSocket, project_id: str):
    await manager.connect(f"progress:{project_id}", websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(f"progress:{project_id}", websocket)


@router.websocket("/ws/publish/{project_id}")
async def publish_ws(websocket: WebSocket, project_id: str):
    await manager.connect(f"publish:{project_id}", websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(f"publish:{project_id}", websocket)


async def send_progress(project_id: str, data: dict):
    await manager.broadcast(f"progress:{project_id}", data)


async def send_publish_status(project_id: str, data: dict):
    await manager.broadcast(f"publish:{project_id}", data)


# ---------- 同步推送辅助函数（供 Celery 任务调用） ----------
def broadcast_progress(project_id: str, data: dict):
    """
    从 Celery 同步任务中推送进度。
    Celery worker 与 FastAPI 进程分离，manager.active_connections 在 worker 进程内为空，
    但保留此调用用于同进程场景；跨进程推送应通过 Redis pubsub（后续可扩展）。
    """
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(manager.broadcast(f"progress:{project_id}", data), loop=loop)
            else:
                loop.run_until_complete(manager.broadcast(f"progress:{project_id}", data))
        except RuntimeError:
            asyncio.run(manager.broadcast(f"progress:{project_id}", data))
    except Exception as e:
        logger.debug(f"进度推送失败(非致命): {e}")


def broadcast_publish_status(project_id: str, data: dict):
    """从 Celery 同步任务中推送发布状态。"""
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(manager.broadcast(f"publish:{project_id}", data), loop=loop)
            else:
                loop.run_until_complete(manager.broadcast(f"publish:{project_id}", data))
        except RuntimeError:
            asyncio.run(manager.broadcast(f"publish:{project_id}", data))
    except Exception as e:
        logger.debug(f"发布状态推送失败(非致命): {e}")