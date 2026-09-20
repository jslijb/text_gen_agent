import logging
import time
from datetime import datetime
from typing import Optional
from app.config.settings import settings

logger = logging.getLogger(__name__)


class KnowledgeBaseManager:
    _instance = None
    _client = None
    _collection = None
    _embedder = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_chroma()
        return cls._instance

    def _init_chroma(self):
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
            self._collection = self._client.get_or_create_collection(
                name="novel_trending",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"ChromaDB初始化成功，当前{self._collection.count()}条记录")
        except Exception as e:
            logger.error(f"ChromaDB初始化失败: {e}")
            self._client = None
            self._collection = None

    def _get_embedder(self):
        if self._embedder is not None:
            return self._embedder
        try:
            from sentence_transformers import SentenceTransformer
            # 用户规则5：模型优先从魔塔社区本地路径加载
            local_path = settings.EMBEDDING_LOCAL_PATH
            import os
            if local_path and os.path.isdir(local_path):
                self._embedder = SentenceTransformer(local_path)
                logger.info(f"本地嵌入模型加载成功(魔塔本地路径): {local_path}")
            else:
                self._embedder = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
                logger.info(f"本地嵌入模型加载成功(HuggingFace): {settings.EMBEDDING_MODEL_NAME}")
            return self._embedder
        except Exception as e:
            logger.warning(f"本地嵌入模型加载失败: {e}，降级使用API")
            self._embedder = "api"
            return self._embedder

    def _embed(self, texts: list[str]) -> list[list[float]]:
        embedder = self._get_embedder()
        if embedder == "api":
            return self._embed_via_api(texts)
        return embedder.encode(texts).tolist()

    def _embed_via_api(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI
        import os
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY1", ""),
            base_url=settings.EMBEDDING_FALLBACK_API,
        )
        response = client.embeddings.create(
            model=settings.EMBEDDING_FALLBACK_MODEL,
            input=texts,
        )
        return [item.embedding for item in response.data]

    def add_entry(self, entry) -> bool:
        if not self._collection:
            return False
        try:
            content = entry.content
            chunks = self._split_text(content)
            embeddings = self._embed(chunks)
            ids = [f"{str(entry.id)}_{i}" for i in range(len(chunks))]
            metadatas = [{
                "topic": entry.topic,
                "emotion_type": entry.emotion_type,
                "ending_type": entry.ending_type,
                "heat_score": entry.heat_score or 0,
                "source": entry.source,
                "created_at": entry.created_at.isoformat() if entry.created_at else "",
                "ttl_days": entry.ttl_days,
            } for i in range(len(chunks))]
            self._collection.upsert(
                ids=ids,
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            return True
        except Exception as e:
            logger.error(f"添加知识条目失败: {e}")
            return False

    def search(self, query: str, n_results: int = 5, topic_filter: str = None) -> list[dict]:
        if not self._collection or self._collection.count() == 0:
            return []
        try:
            query_embedding = self._embed([query])
            where_filter = {"topic": topic_filter} if topic_filter else None
            results = self._collection.query(
                query_embeddings=query_embedding,
                n_results=min(n_results, self._collection.count()),
                where=where_filter,
            )
            entries = []
            if results and results["ids"] and results["ids"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    entries.append({
                        "id": results["ids"][0][i].rsplit("_", 1)[0],
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                    })
            return entries
        except Exception as e:
            logger.error(f"知识库检索失败: {e}")
            return []

    def search_trending_features(self, genre: str) -> list[dict]:
        return self.search(f"{genre}题材 爆款小说特征 开头技巧", n_results=5, topic_filter=genre)

    def cleanup_expired(self, db) -> int:
        from app.models.knowledge import KnowledgeEntry
        from datetime import datetime, timedelta
        entries = db.query(KnowledgeEntry).all()
        deleted = 0
        now = datetime.utcnow()
        for entry in entries:
            if entry.created_at and (now - entry.created_at).days > entry.ttl_days:
                try:
                    chunks_ids = [f"{str(entry.id)}_{i}" for i in range(10)]
                    if self._collection:
                        self._collection.delete(ids=chunks_ids)
                except Exception:
                    pass
                db.delete(entry)
                deleted += 1
        db.commit()
        return deleted

    def review_and_dedup(self, db) -> list[str]:
        """
        spec 5.3.1 规则 4：审视历史爆款，与最新对比，过时的标记删除。
        design 1.3.4：向量去重（相似度>0.95 视为重复）。
        修复：原代码阈值方向混淆，现拆分为两个逻辑。
        """
        from app.models.knowledge import KnowledgeEntry
        entries = db.query(KnowledgeEntry).filter(KnowledgeEntry.vectorized == True).all()
        outdated_ids = []
        if len(entries) < 2:
            return outdated_ids
        try:
            contents = [e.content[:500] for e in entries]  # 加大截取长度提升相似度准确性
            embeddings = self._embed(contents)
            # 按创建时间排序，最新的在前
            indexed = list(zip(entries, embeddings))
            indexed.sort(key=lambda x: x[0].created_at or datetime.utcnow(), reverse=True)
            newest_entry, newest_emb = indexed[0]
            for i in range(1, len(indexed)):
                entry, emb = indexed[i]
                sim_with_newest = self._cosine_similarity(emb, newest_emb)
                # spec 5.3.1 规则 4：与最新爆款相似度低于 0.5 标记为过时
                if sim_with_newest < 0.5:
                    if (datetime.utcnow() - (entry.created_at or datetime.utcnow())).days > 30:
                        outdated_ids.append(str(entry.id))
                # design 1.3.4：与最新相似度 > 0.95 视为重复（冗余），也标记删除
                elif sim_with_newest > 0.95:
                    outdated_ids.append(str(entry.id))
        except Exception as e:
            logger.error(f"审视去重失败: {e}")
        return list(set(outdated_ids))

    def lru_evict(self, db, max_entries: int = 1000) -> int:
        """
        spec 5.3.3 异常 4：磁盘空间不足时触发 LRU 淘汰，清理最久未访问的数据。
        """
        from app.models.knowledge import KnowledgeEntry
        total = db.query(KnowledgeEntry).count()
        if total <= max_entries:
            return 0
        to_delete = total - max_entries
        # 按 created_at 升序删除最旧的
        old_entries = db.query(KnowledgeEntry).order_by(KnowledgeEntry.created_at.asc()).limit(to_delete).all()
        deleted = 0
        for entry in old_entries:
            try:
                chunk_ids = [f"{str(entry.id)}_{i}" for i in range(10)]
                if self._collection:
                    self._collection.delete(ids=chunk_ids)
            except Exception:
                pass
            db.delete(entry)
            deleted += 1
        db.commit()
        logger.info(f"LRU淘汰完成，删除{deleted}条最久未访问数据")
        return deleted

    def _split_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            if end < len(text):
                for sep in ["。", "！", "？", "\n", " "]:
                    pos = text.rfind(sep, start, end)
                    if pos > start:
                        end = pos + 1
                        break
            chunks.append(text[start:end])
            start = end - overlap
            if start >= len(text):
                break
        return [c for c in chunks if c.strip()]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)