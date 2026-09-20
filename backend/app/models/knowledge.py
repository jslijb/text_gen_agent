import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, Float, Boolean, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.config.database import Base
from app.config.types import GUID


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(String(20), nullable=False)
    word_count_range: Mapped[str] = mapped_column(String(20), nullable=False)
    opening_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    emotion_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ending_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    heat_score: Mapped[float] = mapped_column(Float, nullable=True)
    ttl_days: Mapped[int] = mapped_column(Integer, default=30)
    vectorized: Mapped[bool] = mapped_column(Boolean, default=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("heat_score IS NULL OR heat_score BETWEEN 0 AND 100", name="ck_knowledge_heat_score"),
        CheckConstraint("emotion_type IN ('thrill','heartbreak','tension','warmth','reversal')", name="ck_knowledge_emotion_type"),
        CheckConstraint("ending_type IN ('happy','open','reversal','tragic')", name="ck_knowledge_ending_type"),
    )
