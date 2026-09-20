"""
日志系统配置（用户规则6：运行日志和错误日志都需要有，永久保存，手动清理）
- 运行日志：logs/app.log（INFO及以上，RotatingFileHandler 10MB×10）
- 错误日志：logs/error.log（ERROR及以上，单独文件便于排错）
- LLM 调用日志：logs/llm_calls.log（记录模型名/token/耗时/状态码，spec 4.4 可维护性2）
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from app.config.settings import settings


def setup_logging():
    """初始化全局日志配置，应在进程入口（FastAPI/Celery/start.py）最早调用一次。"""
    os.makedirs(settings.LOGS_DIR, exist_ok=True)

    root = logging.getLogger()
    # 避免重复初始化导致 handler 叠加
    if getattr(root, "_novel_logging_configured", False):
        return
    root.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(processName)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 运行日志（INFO 及以上）
    app_handler = RotatingFileHandler(
        os.path.join(settings.LOGS_DIR, "app.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(fmt)
    root.addHandler(app_handler)

    # 错误日志（ERROR 及以上，独立文件便于排错）
    err_handler = RotatingFileHandler(
        os.path.join(settings.LOGS_DIR, "error.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=20,
        encoding="utf-8",
    )
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(fmt)
    root.addHandler(err_handler)

    # 控制台输出（开发时方便查看）
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    # LLM 调用专用日志（spec 4.4 可维护性2：模型名/token用量/耗时/状态码）
    llm_logger = logging.getLogger("llm_call")
    llm_handler = RotatingFileHandler(
        os.path.join(settings.LOGS_DIR, "llm_calls.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    llm_handler.setLevel(logging.INFO)
    llm_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    llm_logger.addHandler(llm_handler)
    llm_logger.propagate = False  # 不向 root 传播，避免重复

    root._novel_logging_configured = True


def get_llm_logger() -> logging.Logger:
    """获取 LLM 调用专用日志器"""
    return logging.getLogger("llm_call")
