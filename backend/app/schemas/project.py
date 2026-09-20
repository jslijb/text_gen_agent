from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional, Any


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    synopsis: str = Field(..., min_length=10, max_length=2000)
    # 2026-09-14 平台化：目标平台决定下面的 channel/genre 合法取值域
    platform: str = Field(default="baidu", description="目标平台：baidu / fanqie")
    # spec v1.4.0：新增 gender（一级分类），genre 为二级分类
    # 平台化后 gender 承载"频道"：百度→男性向/女性向/无性向；番茄→女频/男频
    gender: str = Field(default="无性向", description="频道：百度为男性向/女性向/无性向，番茄为女频/男频")
    genre: str = Field(...)
    target_word_count: int = Field(..., ge=10000, le=300000)
    initial_chapters: int = Field(default=10, ge=1, le=50)
    total_chapters: int = Field(default=30, ge=10, le=200)
    daily_chapters: int = Field(default=2, ge=1, le=5)
    daily_publish_time: str = Field(default="08:00", pattern=r"^\d{2}:\d{2}$")


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    synopsis: Optional[str] = Field(None, min_length=10, max_length=2000)
    platform: Optional[str] = None
    gender: Optional[str] = None
    genre: Optional[str] = None
    target_word_count: Optional[int] = Field(None, ge=10000, le=300000)
    initial_chapters: Optional[int] = Field(None, ge=1, le=50)
    total_chapters: Optional[int] = Field(None, ge=10, le=200)
    daily_chapters: Optional[int] = Field(None, ge=1, le=5)
    daily_publish_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    synopsis: str
    platform: str  # 2026-09-14 平台化：baidu / fanqie
    gender: str  # spec v1.4.0：新增；平台化后承载"频道"
    genre: str
    target_word_count: int
    initial_chapters: int
    total_chapters: int
    daily_chapters: int
    daily_publish_time: str
    status: str
    outline: Optional[dict] = None
    characters: Optional[Any] = None
    foreshadowing_plan: Optional[Any] = None
    cover_url: Optional[str] = None  # spec 6.1 字段11：封面URL
    titles: Optional[list[str]] = None  # 百度平台分发标题列表
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    total: int
    items: list[ProjectResponse]