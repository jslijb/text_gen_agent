import pytest
from unittest.mock import patch, MagicMock
from app.services.publisher import Publisher
from pathlib import Path


class TestPublisher:
    def setup_method(self):
        Publisher._instance = None

    def test_singleton(self):
        p1 = Publisher()
        p2 = Publisher()
        assert p1 is p2

    def test_encrypt_decrypt_roundtrip(self):
        # 加密函数现为模块级（AES-256-GCM），通过 cookie_manager 测试
        from app.utils.cookie_manager import CookieManager
        from app.config.settings import settings
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            cm = CookieManager(os.path.join(td, "cookies.json"), settings.COOKIE_ENCRYPTION_KEY)
            original = '[{"name": "test", "value": "123"}]'
            encrypted = cm._encrypt(original)
            decrypted = cm._decrypt(encrypted)
            assert decrypted == original

    def test_load_cookies_no_file(self):
        with patch.object(Publisher, '__init__', lambda self: None):
            pub = Publisher()
            pub._cookie_path = Path("/nonexistent/cookies.json")
            result = pub.load_cookies()
            assert result == []

    def test_publish_no_cookies(self):
        with patch.object(Publisher, '__init__', lambda self: None):
            pub = Publisher()
            pub._cookie_path = Path("/nonexistent/cookies.json")
            result = pub.publish_chapter("测试小说", "第1章", "内容")
            assert result["success"] is False
            assert "Cookie" in result["error"]