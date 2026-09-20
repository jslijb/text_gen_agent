import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, Float, Boolean, DateTime, CheckConstraint, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.config.database import Base
from app.config.types import GUID, JSONType


class ModelUsage(Base):
    __tablename__ = "model_usage"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="available")
    month_period: Mapped[str] = mapped_column(String(7), nullable=False)

    __table_args__ = (
        UniqueConstraint("model_name", "month_period", name="uq_model_usage_month"),
        CheckConstraint("status IN ('available','exhausted','unreachable')", name="ck_model_usage_status"),
    )


class RuntimeConfig(Base):
    __tablename__ = "runtime_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    effective: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Foreshadowing(Base):
    __tablename__ = "foreshadowing"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    planted_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    advanced_chapters: Mapped[str] = mapped_column(Text, default="[]")
    resolved_chapter: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planted")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="foreshadowings")

    __table_args__ = (
        CheckConstraint("status IN ('planted','advanced','resolved','overdue')", name="ck_foreshadowing_status"),
    )


class PublishQueue(Base):
    __tablename__ = "publish_queue"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chapter: Mapped["Chapter"] = relationship(back_populates="publish_queue_items")

    __table_args__ = (
        CheckConstraint("status IN ('pending','processing','completed','failed')", name="ck_publish_queue_status"),
    )
