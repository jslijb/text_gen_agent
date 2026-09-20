"""封面生成 Pydantic Schema（spec 5.8 / design 2.2 封面生成）"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


# spec 5.8.1 规则2：作品性向枚举
GenderLiteral = Literal["男性向", "女性向", "无性向"]


class CoverGenerateRequest(BaseModel):
    """封面生成请求"""
    gender: GenderLiteral = Field(default="无性向", description="作品性向")
    genre: str = Field(..., min_length=1, max_length=20, description="作品类型")


class CoverGenerateResponse(BaseModel):
    """封面生成响应"""
    model_config = {"protected_namespaces": ()}
    cover_url: str = Field(..., description="封面访问 URL，如 /static/covers/xxx.png")
    prompt_used: str = Field(..., description="实际使用的文生图 Prompt")
    model_used: str = Field(default="agnes-image-2.1-flash", description="文生图模型名")


class CoverResponse(BaseModel):
    """封面查询响应"""
    cover_url: Optional[str] = Field(None, description="封面 URL，无封面时为 null")
