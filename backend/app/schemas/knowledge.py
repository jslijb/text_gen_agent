from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional


class KnowledgeCreate(BaseModel):
    topic: str = Field(..., max_length=20)
    word_count_range: str = Field(..., max_length=20)
    opening_pattern: str
    emotion_type: str = Field(..., pattern="^(thrill|heartbreak|tension|warmth|reversal)$")
    ending_type: str = Field(..., pattern="^(happy|open|reversal|tragic)$")
    source: str = Field(..., max_length=100)
    heat_score: Optional[float] = Field(None, ge=0, le=100)
    ttl_days: int = Field(default=30, ge=1)
    content: str


class KnowledgeUpdate(BaseModel):
    topic: Optional[str] = Field(None, max_length=20)
    word_count_range: Optional[str] = Field(None, max_length=20)
    opening_pattern: Optional[str] = None
    emotion_type: Optional[str] = Field(None, pattern="^(thrill|heartbreak|tension|warmth|reversal)$")
    ending_type: Optional[str] = Field(None, pattern="^(happy|open|reversal|tragic)$")
    source: Optional[str] = Field(None, max_length=100)
    heat_score: Optional[float] = Field(None, ge=0, le=100)
    ttl_days: Optional[int] = Field(None, ge=1)
    content: Optional[str] = None


class KnowledgeResponse(BaseModel):
    id: UUID
    topic: str
    word_count_range: str
    opening_pattern: str
    emotion_type: str
    ending_type: str
    source: str
    heat_score: Optional[float] = None
    ttl_days: int
    vectorized: bool
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    n_results: int = Field(default=5, ge=1, le=20)
    topic_filter: Optional[str] = None


class KnowledgeListResponse(BaseModel):
    total: int
    items: list[KnowledgeResponse]


class KnowledgeStatsResponse(BaseModel):
    total_entries: int
    vectorized_entries: int
    topics: dict[str, int]
    avg_heat_score: float