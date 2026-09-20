from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.models.config import RuntimeConfig, ModelUsage
from app.schemas.config import ConfigUpdate, ConfigResponse, ModelConfigResponse, ModelReloadResponse
from datetime import datetime

router = APIRouter(prefix="/config", tags=["配置管理"])


@router.get("", response_model=list[ConfigResponse])
async def list_config(db: Session = Depends(get_db)):
    configs = db.query(RuntimeConfig).all()
    return [ConfigResponse(
        key=c.key,
        value=c.value,
        description=c.description,
        effective=c.effective,
        updated_at=c.updated_at.isoformat() if c.updated_at else ""
    ) for c in configs]


@router.put("/{key}", response_model=ConfigResponse)
async def update_config(key: str, data: ConfigUpdate, db: Session = Depends(get_db)):
    config = db.query(RuntimeConfig).filter(RuntimeConfig.key == key).first()
    if config:
        config.value = data.value
        if data.description is not None:
            config.description = data.description
        config.updated_at = datetime.utcnow()
    else:
        config = RuntimeConfig(key=key, value=data.value, description=data.description)
        db.add(config)
    db.commit()
    db.refresh(config)
    return ConfigResponse(
        key=config.key,
        value=config.value,
        description=config.description,
        effective=config.effective,
        updated_at=config.updated_at.isoformat() if config.updated_at else ""
    )


@router.get("/models", response_model=list[ModelConfigResponse])
async def list_models(db: Session = Depends(get_db)):
    from app.services.model_manager import ModelManager
    mgr = ModelManager()
    models = mgr.get_all_models_status()
    current_month = datetime.utcnow().strftime("%Y-%m")
    result = []
    for m in models:
        usage = db.query(ModelUsage).filter(
            ModelUsage.model_name == m["name"],
            ModelUsage.month_period == current_month
        ).first()
        result.append(ModelConfigResponse(
            name=m["name"],
            base_url=m["base_url"],
            api_key_env=m["api_key_env"],
            quota=m["quota"],
            priority=m["priority"],
            role=m.get("role"),
            tokens_used=usage.tokens_used if usage else 0,
            call_count=usage.call_count if usage else 0,
            status=usage.status if usage else "available"
        ))
    return result


@router.post("/models/reload", response_model=ModelReloadResponse)
async def reload_models():
    from app.services.model_manager import ModelManager
    mgr = ModelManager()
    count = mgr.reload_config()
    return ModelReloadResponse(success=True, message="模型配置已重载", models_count=count)