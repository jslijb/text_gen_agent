import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, CheckConstraint, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.config.database import Base
from app.config.types import GUID, JSONType


class VideoTask(Base):
    __tablename__ = "video_tasks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scene_id: Mapped[int] = mapped_column(Integer, nullable=False)
    scene_data: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    agnes_task_id: Mapped[str] = mapped_column(String(100), nullable=True)
    agnes_video_id: Mapped[str] = mapped_column(String(100), nullable=True)
    video_url: Mapped[str] = mapped_column(String(500), nullable=True)
    audio_url: Mapped[str] = mapped_column(String(500), nullable=True)
    subtitle_url: Mapped[str] = mapped_column(String(500), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    platform: Mapped[str] = mapped_column(String(20), default="douyin")
    style: Mapped[str] = mapped_column(String(50), default="中国风水墨")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="video_tasks")

    __table_args__ = (
        CheckConstraint("status IN ('pending','queued','in_progress','completed','failed')", name="ck_video_task_status"),
        CheckConstraint("retry_count BETWEEN 0 AND 3", name="ck_video_task_retry_count"),
        UniqueConstraint("project_id", "chapter_number", "scene_id", name="uq_video_task_scene"),
    )

    VALID_STATUSES = ["pending", "queued", "in_progress", "completed", "failed"]
    VALID_PLATFORMS = ["douyin", "kuaishou", "weishi", "youku", "iqiyi", "tencent"]
    VALID_STYLES = ["中国风水墨", "日系动漫", "写实风格", "欧美漫画"]