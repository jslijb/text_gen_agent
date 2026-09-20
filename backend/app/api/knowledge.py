from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from app.config.database import get_db
from app.models.knowledge import KnowledgeEntry
from app.schemas.knowledge import (
    KnowledgeCreate, KnowledgeUpdate, KnowledgeResponse,
    KnowledgeListResponse, KnowledgeSearchRequest, KnowledgeStatsResponse
)

router = APIRouter(prefix="/knowledge", tags=["知识库管理"])


@router.get("", response_model=KnowledgeListResponse)
async def list_knowledge(skip: int = 0, limit: int = 20, topic: str = None, db: Session = Depends(get_db)):
    query = db.query(KnowledgeEntry)
    if topic:
        query = query.filter(KnowledgeEntry.topic == topic)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return KnowledgeListResponse(total=total, items=items)


@router.get("/search", response_model=list[KnowledgeResponse])
async def search_knowledge(
    query: str = Query(..., min_length=1, description="搜索关键词"),
    n_results: int = Query(5, ge=1, le=20),
    topic_filter: str = Query(None, description="题材过滤"),
    db: Session = Depends(get_db),
):
    """spec 2.2：知识库语义搜索（GET 方法）"""
    from app.services.knowledge_base import KnowledgeBaseManager
    kb = KnowledgeBaseManager()
    results = kb.search(query, n_results=n_results, topic_filter=topic_filter)
    entry_ids = [r["id"] for r in results] if results else []
    entries = db.query(KnowledgeEntry).filter(KnowledgeEntry.id.in_(entry_ids)).all() if entry_ids else []
    return entries


@router.post("", response_model=KnowledgeResponse, status_code=201)
async def create_knowledge(data: KnowledgeCreate, db: Session = Depends(get_db)):
    entry = KnowledgeEntry(**data.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    from app.services.knowledge_base import KnowledgeBaseManager
    kb = KnowledgeBaseManager()
    kb.add_entry(entry)
    return entry


@router.put("/{entry_id}", response_model=KnowledgeResponse)
async def update_knowledge(entry_id: UUID, data: KnowledgeUpdate, db: Session = Depends(get_db)):
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
async def delete_knowledge(entry_id: UUID, db: Session = Depends(get_db)):
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    db.delete(entry)
    db.commit()


@router.post("/scrape", status_code=202)
async def scrape_trending():
    from app.tasks.knowledge_tasks import scrape_trending_novels
    scrape_trending_novels.delay()
    return {"message": "爆款抓取任务已提交"}


@router.post("/cleanup", status_code=202)
async def cleanup_expired():
    from app.tasks.knowledge_tasks import cleanup_knowledge_base
    cleanup_knowledge_base.delay()
    return {"message": "过期清理任务已提交"}


@router.get("/stats", response_model=KnowledgeStatsResponse)
async def knowledge_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    total = db.query(KnowledgeEntry).count()
    vectorized = db.query(KnowledgeEntry).filter(KnowledgeEntry.vectorized == True).count()
    topic_counts = dict(db.query(KnowledgeEntry.topic, func.count(KnowledgeEntry.id)).group_by(KnowledgeEntry.topic).all())
    avg_heat = db.query(func.avg(KnowledgeEntry.heat_score)).scalar() or 0.0
    return KnowledgeStatsResponse(
        total_entries=total,
        vectorized_entries=vectorized,
        topics=topic_counts,
        avg_heat_score=round(avg_heat, 2)
    )