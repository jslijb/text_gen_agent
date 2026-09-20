"""热点创意生成 Pydantic Schema（对应 design.md 热点数据与创意生成 API）"""
from typing import List, Literal
from pydantic import BaseModel, Field


# 题材枚举与 Project.VALID_GENRES_BY_GENDER 对齐（spec v1.4.0 百度作家平台官方二级分类）
GenreLiteral = Literal[
    # 男性向
    "都市情感", "历史故事",
    # 女性向
    "现代言情", "古代言情", "青春校园", "婚姻家庭",
    # 无性向
    "恐怖推理", "乡村故事", "真实故事", "见闻杂谈", "复仇爽文", "特殊职业",
]


class HotTopic(BaseModel):
    rank: int
    title: str
    author: str
    genre: str
    gender: str = ""  # spec v1.4.1：百度 genre 映射的性向（男性向/女性向/无性向）
    hot_index: int
    description: str


class GenreDistribution(BaseModel):
    genre: str
    count: int
    percentage: float


class HotNovelsResponse(BaseModel):
    source: str
    degraded: bool
    fetched_at: str
    cache_ttl_seconds: int
    topics: List[HotTopic]
    genre_distribution: List[GenreDistribution]


class GenerateSynopsisRequest(BaseModel):
    genre: GenreLiteral
    reference_topics: List[str] = Field(default=[], description="参考的热门小说书名列表")
    count: int = Field(default=3, ge=1, le=5)


class GenerateSynopsisResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    synopses: List[str]
    degraded: bool = False
    model_used: str


class GenerateTitleRequest(BaseModel):
    synopsis: str = Field(..., min_length=10, description="选定的故事梗概")
    genre: GenreLiteral
    count: int = Field(default=5, ge=1, le=10)


class GenerateTitleResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    titles: List[str]
    model_used: str
