import logging
import yaml
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from app.config.settings import settings

logger = logging.getLogger(__name__)


class ModelsConfigHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback
        self._last_modified = 0

    def on_modified(self, event):
        if event.src_path.endswith("models.yaml"):
            current_time = time.time()
            if current_time - self._last_modified < 1:
                return
            self._last_modified = current_time
            logger.info(f"检测到模型配置文件变更: {event.src_path}")
            self.callback()


class ConfigService:
    _observer = None

    @classmethod
    def start_watching(cls):
        if cls._observer is not None:
            return
        config_dir = str(Path(settings.MODELS_CONFIG_PATH).parent)
        handler = ModelsConfigHandler(cls._on_models_config_changed)
        cls._observer = Observer()
        cls._observer.schedule(handler, config_dir, recursive=False)
        cls._observer.daemon = True
        cls._observer.start()
        logger.info(f"已开始监听配置目录: {config_dir}")

    @classmethod
    def stop_watching(cls):
        if cls._observer:
            cls._observer.stop()
            cls._observer.join()
            cls._observer = None

    @staticmethod
    def _on_models_config_changed():
        try:
            from app.services.model_manager import ModelManager
            mgr = ModelManager()
            count = mgr.reload_config()
            logger.info(f"模型配置已热加载，共{count}个模型")
        except Exception as e:
            logger.error(f"模型配置热加载失败: {e}")

    @staticmethod
    def load_models_config() -> dict:
        config_path = settings.MODELS_CONFIG_PATH
        if not Path(config_path).exists():
            return {"models": []}
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def validate_models_config(config: dict) -> tuple[bool, str]:
        models = config.get("models", [])
        if not models:
            return False, "模型配置为空"
        required_fields = ["name", "base_url", "api_key_env", "quota", "priority"]
        for i, m in enumerate(models):
            for field in required_fields:
                if field not in m:
                    return False, f"第{i + 1}个模型缺少必填字段: {field}"
        return True, "配置有效"