from typing import Optional, List
from pydantic import BaseModel, Field


class SceneItem(BaseModel):
    scene_id: int = Field(..., ge=1)
    visual_prompt: str = Field(..., min_length=10)
    dialogue: Optional[str] = None
    narration: Optional[str] = None
    camera_movement: str = Field(default="static", pattern="^(static|pan_left|pan_right|zoom_in|zoom_out|tracking)$")
    duration_seconds: int = Field(default=8, ge=5, le=18)


class SplitScenesRequest(BaseModel):
    chapter_number: int = Field(..., ge=1)
    style: str = Field(default="中国风水墨")
    platform: str = Field(default="douyin")


class SplitScenesResponse(BaseModel):
    chapter_number: int
    scenes: List[SceneItem]
    model_used: str


class GenerateVideoRequest(BaseModel):
    chapter_number: int = Field(..., ge=1)
    platform: str = Field(default="douyin")
    style: str = Field(default="中国风水墨")


class GenerateVideoResponse(BaseModel):
    task_id: str
    message: str
    chapter_number: int
    scene_count: int


class SceneStatus(BaseModel):
    scene_id: int
    status: str
    video_url: Optional[str] = None


class VideoStatusResponse(BaseModel):
    chapter_number: int
    overall_status: str
    progress: float = Field(..., ge=0, le=1)
    scenes: List[SceneStatus]
    final_video_url: Optional[str] = None


class VideoTaskResponse(BaseModel):
    chapter_number: int
    video_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    file_size_mb: Optional[float] = None
    platform: str
    created_at: Optional[str] = None


class VideoListItem(BaseModel):
    chapter_number: int
    video_url: Optional[str] = None
    status: str
    scene_count: int
    platform: str


class UpdateScenesRequest(BaseModel):
    chapter_number: int = Field(..., ge=1)
    scenes: List[SceneItem]