"""
嵌入模型封装（design 第111行 / Task 5.1）
优先使用本地 bge-large-zh-v1.5（魔塔社区下载），降级到百炼 text-embedding-v4 API。
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Embedder:
    """嵌入模型封装，支持本地模型与 API 降级"""

    def __init__(self):
        self._model = None
        self._mode: Optional[str] = None  # "local" | "api"

    def _load(self):
        if self._model is not None:
            return
        from app.config.settings import settings
        # 优先本地路径（魔塔社区下载，用户规则5）
        try:
            from sentence_transformers import SentenceTransformer
            local_path = settings.EMBEDDING_LOCAL_PATH
            if local_path and os.path.isdir(local_path):
                self._model = SentenceTransformer(local_path)
                self._mode = "local"
                logger.info(f"嵌入模型加载成功(魔塔本地): {local_path}")
            else:
                self._model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
                self._mode = "local"
                logger.info(f"嵌入模型加载成功(HuggingFace): {settings.EMBEDDING_MODEL_NAME}")
        except Exception as e:
            logger.warning(f"本地嵌入模型加载失败，降级到API: {e}")
            self._model = "api"
            self._mode = "api"

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._load()
        if self._mode == "api":
            return self._embed_via_api(texts)
        return self._model.encode(texts).tolist()

    def _embed_via_api(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI
        from app.config.settings import settings
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY1", ""),
            base_url=settings.EMBEDDING_FALLBACK_API,
        )
        response = client.embeddings.create(
            model=settings.EMBEDDING_FALLBACK_MODEL,
            input=texts,
        )
        return [item.embedding for item in response.data]

    @property
    def mode(self) -> Optional[str]:
        return self._mode
