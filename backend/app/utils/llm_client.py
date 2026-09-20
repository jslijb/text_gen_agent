"""
LLM 客户端封装（design 第110行 / Task 2.1）
基于 openai 库的 OpenAI 兼容客户端，封装流式/非流式调用与 token 计数。
实际模型选择与自动切换由 services/model_manager.py 负责，本模块提供底层调用工具。
"""
import logging
from typing import Optional, Generator
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI 兼容 LLM 客户端封装"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 4096) -> tuple[str, int]:
        """非流式调用，返回 (结果文本, token用量)"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0
        return text, tokens

    def chat_stream(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 4096) -> Generator[str, None, None]:
        """流式调用，逐 token 返回"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """粗略估算 token 数（中文约 1.5 字/token，英文约 4 字符/token）"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
