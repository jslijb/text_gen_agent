import os
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI小说生成系统"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_novel")
    REDIS_URL: str = "redis://localhost:6379/0"

    CHROMA_PERSIST_DIR: str = str(Path(__file__).parent.parent.parent.parent / "data" / "chroma_db")
    NOVELS_DIR: str = str(Path(__file__).parent.parent.parent.parent / "data" / "novels")
    COOKIES_DIR: str = str(Path(__file__).parent.parent.parent.parent / "data" / "cookies")
    LOGS_DIR: str = str(Path(__file__).parent.parent.parent.parent / "logs")
    MODELS_CONFIG_PATH: str = str(Path(__file__).parent.parent.parent.parent / "config" / "models.yaml")
    # spec 5.8.1 规则5：封面存储目录（通过 StaticFiles 挂载到 /static）
    COVERS_DIR: str = str(Path(__file__).parent.parent / "static" / "covers")
    STATIC_DIR: str = str(Path(__file__).parent.parent / "static")
    VIDEOS_DIR: str = str(Path(__file__).parent.parent / "static" / "videos")
    BGM_DIR: str = str(Path(__file__).parent.parent / "static" / "bgm")

    COOKIE_ENCRYPTION_KEY: str = os.getenv("COOKIE_ENCRYPTION_KEY", "default-key-change-in-production-32b!")

    # sieve 抓取 API（https://scrape.usesieve.com）——密钥存 backend/.env，随 env_file 注入
    # backend / worker / beat 三个容器。未配置时 SIEVE_API_KEY 为空，抓取相关功能整体关闭，
    # 其余功能不受影响（见 app/services/sieve_client.py）。
    SIEVE_BASE_URL: str = os.getenv("SIEVE_BASE_URL", "https://scrape.usesieve.com")
    SIEVE_API_KEY: str = os.getenv("SIEVE_API_KEY", "")
    # sieve 交付文件（files[]）落盘目录，与 novels/cookies 同级放在 data/ 下
    SIEVE_FILES_DIR: str = str(Path(__file__).parent.parent.parent.parent / "data" / "sieve")

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # 嵌入模型：优先从魔塔社区本地路径加载（用户规则5）
    # 模型存储在 D:\models\modelscope，目录名 bge-large-zh-v1___5 是魔塔下载后的实际目录
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-large-zh-v1.5"
    EMBEDDING_LOCAL_PATH: str = os.getenv("EMBEDDING_LOCAL_PATH", r"D:\models\modelscope\BAAI\bge-large-zh-v1___5")
    EMBEDDING_FALLBACK_API: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_FALLBACK_MODEL: str = "text-embedding-v4"

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    HUMANIZE_FORBIDDEN_PATTERNS_COUNT: int = 23

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()