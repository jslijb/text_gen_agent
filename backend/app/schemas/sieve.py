"""sieve 抓取 API 的 Pydantic Schema。

字段名与 sieve 契约一一对应（instruction / target_urls / fields / schema /
output_schema / table_shape / compliance_mode），不另起一套命名。
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

ComplianceMode = Literal["conservative", "regular", "yolo"]
TableShape = Literal["long", "wide"]


class SieveRunRequest(BaseModel):
    """创建 run 与追问共用同一组字段（契约要求 body 一致）。"""

    # 线上字段名必须是 schema，但 Python 属性不能叫 schema ——
    # pydantic 会警告它遮蔽了 BaseModel.schema()，所以属性用别名接。
    model_config = {"protected_namespaces": (), "populate_by_name": True}

    instruction: str = Field(..., min_length=1, description="自然语言的任务说明")
    target_urls: List[str] = Field(default_factory=list, description="公开 http(s) 页面")
    fields: List[str] = Field(default_factory=list, description="期望的列")
    schema_: Optional[Dict[str, Any]] = Field(
        default=None, alias="schema", description="建议性的 JSON Schema"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="严格校验用的 JSON Schema 2020-12（≤32KB）"
    )
    table_shape: Optional[TableShape] = None
    # 默认 regular；yolo 会放宽站点访问策略，只能由用户显式选择
    compliance_mode: ComplianceMode = "regular"


class SieveRunOut(BaseModel):
    model_config = {"protected_namespaces": ()}

    id: str
    session_id: Optional[str] = None
    status: str
    kind: str
    parent_id: Optional[str] = None
    instruction: str
    target_urls: Optional[List[str]] = None
    compliance_mode: str
    turns: int = 0
    summary: Optional[str] = None
    result: Optional[Any] = None
    files: Optional[List[Dict[str, Any]]] = None
    local_files: Optional[List[str]] = None
    # 结论字段：conformance_ok=False 时前端必须显示 warning，不能把结果当干净数据
    schema_conformance: Optional[str] = None
    conformance_ok: Optional[bool] = None
    conformance_warning: Optional[str] = None
    refusal_code: Optional[str] = None
    error: Optional[str] = None
    poll: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SieveRunListResponse(BaseModel):
    items: List[SieveRunOut]
    total: int


class SieveStatusResponse(BaseModel):
    """未配置时前端据此隐藏/置灰入口，其余功能不受影响。"""

    configured: bool
    base_url: str
    compliance_modes: List[str]


class SieveCreditsResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    plan: Optional[str] = None
    limit: Optional[float] = None
    used: Optional[float] = None
    remaining: Optional[float] = None
    raw: Dict[str, Any] = Field(default_factory=dict)
