import logging
from typing import Optional
from app.services.model_manager import ModelManager

logger = logging.getLogger(__name__)


class BaseAgent:
    def __init__(self, role: str, temperature: float = 0.7):
        self.role = role
        self.temperature = temperature
        self.model_manager = ModelManager()

    def execute(self, prompt: str, system_prompt: str = None, max_tokens: int = 4096) -> str:
        return self.model_manager.call_llm(
            prompt=prompt,
            role=self.role,
            system_prompt=system_prompt,
            temperature=self.temperature,
            max_tokens=max_tokens,
        )