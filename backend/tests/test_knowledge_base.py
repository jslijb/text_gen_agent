import pytest
from unittest.mock import patch, MagicMock
from app.services.knowledge_base import KnowledgeBaseManager


class TestKnowledgeBaseManager:
    def setup_method(self):
        KnowledgeBaseManager._instance = None

    def test_singleton(self):
        with patch.object(KnowledgeBaseManager, '_init_chroma'):
            kb1 = KnowledgeBaseManager()
            kb2 = KnowledgeBaseManager()
            assert kb1 is kb2

    def test_split_text_short(self):
        with patch.object(KnowledgeBaseManager, '_init_chroma'):
            kb = KnowledgeBaseManager()
            result = kb._split_text("短文本")
            assert len(result) == 1
            assert result[0] == "短文本"

    def test_split_text_long(self):
        with patch.object(KnowledgeBaseManager, '_init_chroma'):
            kb = KnowledgeBaseManager()
            text = "这是一段很长的文本。" * 200
            result = kb._split_text(text, chunk_size=500, overlap=50)
            assert len(result) > 1
            for chunk in result:
                assert len(chunk) <= 600

    def test_cosine_similarity(self):
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        score = KnowledgeBaseManager._cosine_similarity(a, b)
        assert abs(score - 1.0) < 0.01

        a = [1.0, 0.0]
        b = [0.0, 1.0]
        score = KnowledgeBaseManager._cosine_similarity(a, b)
        assert abs(score) < 0.01

    def test_search_empty_collection(self):
        with patch.object(KnowledgeBaseManager, '_init_chroma'):
            kb = KnowledgeBaseManager()
            kb._collection = None
            result = kb.search("测试查询")
            assert result == []