"""热点数据与创意生成 API（对应 spec 5.4）"""
import logging
from fastapi import APIRouter, HTTPException, Query

from app.schemas.hot_topic import (
    HotNovelsResponse, GenerateSynopsisRequest, GenerateSynopsisResponse,
    GenerateTitleRequest, GenerateTitleResponse,
)
from app.services.hot_topic_fetcher import (
    HotTopicFetcher, HotTopicUnavailable, generate_synopses, generate_titles,
)

router = APIRouter(prefix="/hot-topics", tags=["hot-topics"])
logger = logging.getLogger(__name__)


@router.get("/novel", response_model=HotNovelsResponse)
async def get_hot_novels(
    force_refresh: bool = Query(False, description="绕过缓存强制刷新"),
    top_n: int = Query(20, ge=1, le=50, description="返回条数上限"),
    gender: str = Query(None, description="按性向筛选（男性向/女性向/无性向），不传返回全部"),
):
    """获取百度热搜小说榜单（带缓存，spec 5.4.1 规则 1/3，v1.4.1 增加性向筛选）"""
    fetcher = HotTopicFetcher()
    try:
        result = fetcher.fetch_hot_novels(force_refresh=force_refresh, top_n=top_n, gender=gender)
        return result
    except HotTopicUnavailable as e:
        logger.error(f"热点获取失败: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/generate-synopsis", response_model=GenerateSynopsisResponse)
async def gen_synopsis(req: GenerateSynopsisRequest):
    """根据热点+题材生成候选梗概（spec 5.4.1 规则 5）"""
    try:
        # 默认注入当前 Top 3 热门书名作为参考
        reference_topics = req.reference_topics
        if not reference_topics:
            fetcher = HotTopicFetcher()
            try:
                hot = fetcher.fetch_hot_novels(top_n=3)
                reference_topics = [t["title"] for t in hot["topics"][:3]]
            except HotTopicUnavailable:
                logger.warning("无热点参考，仅用爆款特征生成梗概")
                reference_topics = []

        synopses, model_used = generate_synopses(
            genre=req.genre, reference_topics=reference_topics, count=req.count
        )
        if not synopses:
            raise HTTPException(status_code=500, detail="LLM 未返回有效梗概")
        return GenerateSynopsisResponse(
            synopses=synopses, degraded=(not reference_topics), model_used=model_used
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成梗概失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成梗概失败: {e}")


@router.post("/generate-title", response_model=GenerateTitleResponse)
async def gen_title(req: GenerateTitleRequest):
    """根据梗概生成候选标题（spec 5.4.1 规则 6）"""
    try:
        titles, model_used = generate_titles(
            synopsis=req.synopsis, genre=req.genre, count=req.count
        )
        if not titles:
            raise HTTPException(status_code=500, detail="LLM 未返回有效标题")
        return GenerateTitleResponse(titles=titles, model_used=model_used)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成标题失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成标题失败: {e}")
