from pydantic import BaseModel, Field
from typing import Optional, Any


class ConfigUpdate(BaseModel):
    value: Any
    description: Optional[str] = None


class ConfigResponse(BaseModel):
    key: str
    value: Any
    description: Optional[str] = None
    effective: bool
    updated_at: str

    model_config = {"from_attributes": True}


class ModelConfigResponse(BaseModel):
    name: str
    base_url: str
    api_key_env: str
    quota: int
    priority: int
    role: Optional[str] = None
    tokens_used: int = 0
    call_count: int = 0
    status: str = "available"


class ModelReloadResponse(BaseModel):
    success: bool
    message: str
    models_count: int