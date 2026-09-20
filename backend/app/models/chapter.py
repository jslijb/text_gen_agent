import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, Float, DateTime, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.config.database import Base
from app.config.types import GUID, JSONType


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    original_content: Mapped[str] = mapped_column(Text, nullable=True)
    ai_score_before: Mapped[float] = mapped_column(Float, nullable=True)
    ai_score_after: Mapped[float] = mapped_column(Float, nullable=True)
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    publish_status: Mapped[str] = mapped_column(String(20), default="unpublished")
    model_used: Mapped[str] = mapped_column(String(50), nullable=True)
    humanize_strategy: Mapped[dict] = mapped_column(JSONType(), nullable=True)
    review_comment: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="chapters")
    publish_queue_items: Mapped[list["PublishQueue"]] = relationship(back_populates="chapter", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("project_id", "chapter_number", name="uq_chapter_project_number"),
        CheckConstraint("ai_score_before IS NULL OR ai_score_before BETWEEN 0 AND 100", name="ck_chapter_ai_score_before"),
        CheckConstraint("ai_score_after IS NULL OR ai_score_after BETWEEN 0 AND 100", name="ck_chapter_ai_score_after"),
        CheckConstraint("review_status IN ('pending','approved','rejected')", name="ck_chapter_review_status"),
        CheckConstraint("publish_status IN ('unpublished','publishing','published','under_review','approved','rejected')", name="ck_chapter_publish_status"),
    )
