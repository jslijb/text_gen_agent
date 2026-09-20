import os
import yaml
import logging
import time
from openai import OpenAI
from typing import Optional
from pathlib import Path
from app.config.settings import settings
from app.config.logging_config import get_llm_logger

logger = logging.getLogger(__name__)
llm_call_logger = get_llm_logger()


def _log_llm_call(model_name: str, role: str, tokens: int, duration_ms: int, status_code: int, success: bool, error: str = ""):
    """记录 LLM 调用日志（spec 4.4 可维护性2：模型名/token用量/耗时/状态码）"""
    llm_call_logger.info(
        f"model={model_name} role={role} tokens={tokens} duration_ms={duration_ms} "
        f"status={status_code} success={success} error={error[:200]}"
    )


class ModelConfig:
    def __init__(self, name: str, base_url: str, api_key_env: str, quota: int, priority: int, role: Optional[str] = None):
        self.name = name
        self.base_url = base_url
        self.api_key_env = api_key_env
        self.quota = quota
        self.priority = priority
        self.role = role
        self.status = "available"

    @property
    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "quota": self.quota,
            "priority": self.priority,
            "role": self.role,
            "status": self.status,
        }


class ModelManager:
    _instance = None
    _models: list[ModelConfig] = []
    _current_index: int = 0
    _last_load_time: float = 0
    _config_mtime: float = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _check_config_changed(self) -> bool:
        config_path = settings.MODELS_CONFIG_PATH
        try:
            mtime = Path(config_path).stat().st_mtime
            if mtime != self._config_mtime:
                return True
        except Exception:
            pass
        return False

    def _load_config(self):
        config_path = settings.MODELS_CONFIG_PATH
        if not Path(config_path).exists():
            logger.warning(f"模型配置文件不存在: {config_path}")
            return
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        models = []
        for m in config.get("models", []):
            models.append(ModelConfig(
                name=m["name"],
                base_url=m["base_url"],
                api_key_env=m["api_key_env"],
                quota=m.get("quota", 1000000),
                priority=m.get("priority", 99),
                role=m.get("role"),
            ))
        models.sort(key=lambda x: x.priority)
        self._models = models
        self._current_index = 0
        self._last_load_time = time.time()
        try:
            self._config_mtime = Path(config_path).stat().st_mtime
        except Exception:
            self._config_mtime = 0
        logger.info(f"已加载{len(models)}个模型配置")

    def reload_config(self) -> int:
        self._load_config()
        return len(self._models)

    def get_model_for_role(self, role: str) -> Optional[ModelConfig]:
        if self._check_config_changed():
            logger.info("检测到模型配置文件变更，自动重载")
            self._load_config()
        for m in self._models:
            if m.role == role and m.status == "available":
                return m
        return self._get_current_model()

    def _get_current_model(self) -> Optional[ModelConfig]:
        for m in self._models:
            if m.status == "available":
                return m
        return None

    def _switch_to_next(self, failed_model: ModelConfig):
        failed_model.status = "exhausted"
        logger.info(f"模型 {failed_model.name} 额度耗尽，切换到下一个可用模型")

    def call_llm(self, prompt: str, role: str = None, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        if self._check_config_changed():
            logger.info("检测到模型配置文件变更，自动重载")
            self._load_config()
        max_switches = len(self._models)
        switches = 0
        while switches < max_switches:
            if role:
                model = self.get_model_for_role(role)
            else:
                model = self._get_current_model()
            if not model:
                raise RuntimeError("所有模型均不可用，请检查配置或等待额度重置")
            start_ts = time.time()
            try:
                client = OpenAI(api_key=model.api_key, base_url=model.base_url)
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                response = client.chat.completions.create(
                    model=model.name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                duration_ms = int((time.time() - start_ts) * 1000)
                result = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else 0
                self._record_usage(model.name, tokens_used)
                _log_llm_call(model.name, role or "general", tokens_used, duration_ms, 200, True)
                return result
            except Exception as e:
                duration_ms = int((time.time() - start_ts) * 1000)
                error_str = str(e)
                # 提取状态码
                status_code = 0
                if "403" in error_str or "Forbidden" in error_str:
                    status_code = 403
                elif hasattr(e, "status_code"):
                    status_code = getattr(e, "status_code", 0)
                _log_llm_call(model.name, role or "general", 0, duration_ms, status_code, False, error_str)
                if status_code == 403:
                    logger.warning(f"模型 {model.name} 返回403，尝试切换")
                    self._switch_to_next(model)
                    switches += 1
                    continue
                else:
                    logger.error(f"模型 {model.name} 调用失败: {e}")
                    raise
        raise RuntimeError("所有模型额度已耗尽，请等待下月重置或添加新模型")

    def call_llm_stream(self, prompt: str, role: str = None, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 4096):
        model = self.get_model_for_role(role) if role else self._get_current_model()
        if not model:
            raise RuntimeError("所有模型均不可用")
        client = OpenAI(api_key=model.api_key, base_url=model.base_url)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        stream = client.chat.completions.create(
            model=model.name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _record_usage(self, model_name: str, tokens: int):
        try:
            from app.config.database import SessionLocal
            from app.models.config import ModelUsage
            from datetime import datetime
            db = SessionLocal()
            try:
                current_month = datetime.utcnow().strftime("%Y-%m")
                usage = db.query(ModelUsage).filter(
                    ModelUsage.model_name == model_name,
                    ModelUsage.month_period == current_month
                ).first()
                if usage:
                    usage.tokens_used += tokens
                    usage.call_count += 1
                    usage.last_used_at = datetime.utcnow()
                else:
                    usage = ModelUsage(
                        model_name=model_name,
                        tokens_used=tokens,
                        call_count=1,
                        last_used_at=datetime.utcnow(),
                        month_period=current_month
                    )
                    db.add(usage)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"记录模型用量失败: {e}")

    def get_all_models_status(self) -> list[dict]:
        return [m.to_dict() for m in self._models]