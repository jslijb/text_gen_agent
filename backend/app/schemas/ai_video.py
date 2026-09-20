from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


# ============ 枚举类型 ============

class VideoProjectStatus(str, Enum):
    """视频项目状态"""
    DRAFT = "draft"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoShotStatus(str, Enum):
    """分镜状态"""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class AssetType(str, Enum):
    """素材类型"""
    CHARACTER = "character"
    SCENE = "scene"
    AUDIO = "audio"
    PROP = "prop"


# ============ VideoProject ============

class VideoProjectBase(BaseModel):
    """视频项目基础模型"""
    title: str
    topic: Optional[str] = None
    style: str = "comic"
    target_duration: int = 30
    config: Optional[Dict[str, Any]] = None


class VideoProjectCreate(VideoProjectBase):
    """创建视频项目"""
    pass


class VideoProjectUpdate(BaseModel):
    """更新视频项目"""
    title: Optional[str] = None
    topic: Optional[str] = None
    style: Optional[str] = None
    target_duration: Optional[int] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[VideoProjectStatus] = None


class VideoProject(VideoProjectBase):
    """视频项目完整模型"""
    id: str
    status: VideoProjectStatus
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============ VideoShot ============

class ShotBase(BaseModel):
    """分镜基础模型"""
    project_id: str
    sequence: int
    description: Optional[str] = None
    narration: Optional[str] = None
    duration: int = 5
    image_prompt: Optional[str] = None
    video_prompt: Optional[str] = None


class ShotCreate(ShotBase):
    """创建分镜"""
    pass


class ShotUpdate(BaseModel):
    """更新分镜"""
    sequence: Optional[int] = None
    description: Optional[str] = None
    narration: Optional[str] = None
    duration: Optional[int] = None
    image_prompt: Optional[str] = None
    video_prompt: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    status: Optional[str] = None


class Shot(ShotBase):
    """分镜完整模型"""
    id: str
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============ VideoAsset ============

class AssetBase(BaseModel):
    """素材基础模型"""
    type: AssetType
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AssetCreate(AssetBase):
    """创建素材"""
    pass


class Asset(AssetBase):
    """素材完整模型"""
    id: str
    used_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============ API响应模型 ============

class VideoProjectResponse(BaseModel):
    """视频项目响应"""
    project: VideoProject


class VideoProjectListResponse(BaseModel):
    """视频项目列表响应"""
    projects: List[VideoProject]
    total: int


class ShotResponse(BaseModel):
    """分镜响应"""
    shot: Shot


class ShotListResponse(BaseModel):
    """分镜列表响应"""
    shots: List[Shot]
    total: int


class AssetResponse(BaseModel):
    """素材响应"""
    asset: Asset


class AssetListResponse(BaseModel):
    """素材列表响应"""
    assets: List[Asset]
    total: int


# ============ 任务响应模型 ============

class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    status: str


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str
    progress: Optional[float] = None
    current_step: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None