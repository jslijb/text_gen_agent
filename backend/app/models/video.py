import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.config.database import Base
from app.config.types import GUID, JSONType


class VideoProject(Base):
    """视频项目表"""
    __tablename__ = "video_projects"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=True)
    style: Mapped[str] = mapped_column(String(50), default="comic")
    target_duration: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    config: Mapped[dict] = mapped_column(JSONType(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    shots: Mapped[list["VideoShot"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("target_duration BETWEEN 15 AND 300", name="ck_video_project_duration"),
        CheckConstraint("status IN ('draft','generating','completed','failed')", name="ck_video_project_status"),
    )

    # 视频风格
    VALID_STYLES = ["comic", "realistic", "anime", "3d"]

    # 状态枚举
    class Status:
        DRAFT = "draft"
        GENERATING = "generating"
        COMPLETED = "completed"
        FAILED = "failed"


class VideoShot(Base):
    """分镜表"""
    __tablename__ = "video_shots"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("video_projects.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    narration: Mapped[str] = mapped_column(Text, nullable=True)
    duration: Mapped[int] = mapped_column(Integer, default=5)
    image_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    video_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    video_url: Mapped[str] = mapped_column(String(500), nullable=True)
    audio_url: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["VideoProject"] = relationship(back_populates="shots")
    assets: Mapped[list["VideoAssetShot"]] = relationship(back_populates="shot", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("duration BETWEEN 2 AND 10", name="ck_video_shot_duration"),
        CheckConstraint("status IN ('pending','generating','completed','failed')", name="ck_video_shot_status"),
    )

    # 状态枚举
    class Status:
        PENDING = "pending"
        GENERATING = "generating"
        COMPLETED = "completed"
        FAILED = "failed"


class VideoAsset(Base):
    """素材表"""
    __tablename__ = "video_assets"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSONType(), nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    shots: Mapped[list["VideoAssetShot"]] = relationship(back_populates="asset", cascade="all, delete-orphan")

    # 素材类型枚举
    class Type:
        CHARACTER = "character"
        SCENE = "scene"
        AUDIO = "audio"
        PROP = "prop"


class VideoAssetShot(Base):
    """素材-分镜关联表"""
    __tablename__ = "video_asset_shots"

    asset_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("video_assets.id"), primary_key=True)
    shot_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("video_shots.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(50), nullable=True)

    asset: Mapped["VideoAsset"] = relationship(back_populates="shots")
    shot: Mapped["VideoShot"] = relationship(back_populates="assets")

    # 角色枚举
    class Role:
        CHARACTER = "character"
        BACKGROUND = "background"
        PROP = "prop"