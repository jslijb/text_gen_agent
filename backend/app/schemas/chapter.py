from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional


class ChapterResponse(BaseModel):
    id: UUID
    project_id: UUID
    chapter_number: int
    title: str
    content: str
    original_content: Optional[str] = None
    ai_score_before: Optional[float] = None
    ai_score_after: Optional[float] = None
    review_status: str
    publish_status: str
    model_used: Optional[str] = None
    humanize_strategy: Optional[dict] = None
    review_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class ChapterUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    content: Optional[str] = Field(None, min_length=1)


class ChapterListResponse(BaseModel):
    total: int
    items: list[ChapterResponse]


class HumanizeRequest(BaseModel):
    strategy: str = Field(default="adversarial", pattern="^(quick|default|deep|recursive|adversarial)$")


class ReviewAction(BaseModel):
    comment: Optional[str] = None