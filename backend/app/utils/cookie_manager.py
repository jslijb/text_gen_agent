"""
Cookie 加密管理（design 第112行 / Task 6.1）
AES-256-GCM 加密存储，符合 design 1.3.5 要求。
"""
import os
import json
import base64
import logging
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


class CookieManager:
    """Cookie 加密存储管理器（AES-256-GCM）"""

    def __init__(self, cookie_path: str, encryption_key: str):
        self.cookie_path = Path(cookie_path)
        # 密钥派生为 32 字节（AES-256）
        self._key = encryption_key.encode("utf-8")[:32].ljust(32, b"0")

    def _encrypt(self, data: str) -> str:
        aesgcm = AESGCM(self._key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, data.encode("utf-8"), None)
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def _decrypt(self, encrypted: str) -> str:
        aesgcm = AESGCM(self._key)
        blob = base64.urlsafe_b64decode(encrypted.encode("ascii"))
        nonce, ciphertext = blob[:12], blob[12:]
        return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")

    def save(self, cookies: list[dict]):
        """加密保存 Cookie 列表"""
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(cookies)
        encrypted = self._encrypt(data)
        with open(self.cookie_path, "w", encoding="utf-8") as f:
            f.write(encrypted)
        logger.info("Cookie已加密保存(AES-256-GCM)")

    def load(self) -> list[dict]:
        """加载并解密 Cookie"""
        if not self.cookie_path.exists():
            return []
        try:
            with open(self.cookie_path, "r", encoding="utf-8") as f:
                encrypted = f.read()
            data = self._decrypt(encrypted)
            return json.loads(data)
        except Exception as e:
            logger.error(f"Cookie加载失败: {e}")
            return []

    def exists(self) -> bool:
        return self.cookie_path.exists()
