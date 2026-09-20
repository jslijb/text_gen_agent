"""
Prompt模板加载器

用于加载config/prompts/目录下的Prompt模板文件
"""

import os
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class PromptLoader:
    """Prompt模板加载器"""
    
    _instance = None
    _cache: Dict[str, str] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load(self, filename: str, prompt_name: str) -> str:
        """
        加载Prompt模板
        
        Args:
            filename: 文件名(如 "video.yaml")
            prompt_name: Prompt名称(如 "topic_generation")
            
        Returns:
            Prompt模板文本
        """
        # 检查缓存
        cache_key = f"{filename}:{prompt_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 加载文件
        prompt_dir = os.path.join(os.path.dirname(__file__), "prompts")
        filepath = os.path.join(prompt_dir, filename)
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Prompt文件不存在: {filepath}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 提取指定Prompt
        prompt = self._extract_prompt(content, prompt_name)
        
        # 缓存
        self._cache[cache_key] = prompt
        
        logger.info(f"加载Prompt模板: {filename} -> {prompt_name}")
        
        return prompt
    
    def _extract_prompt(self, content: str, prompt_name: str) -> str:
        """从YAML内容中提取Prompt"""
        # 匹配格式: prompt_name: |
        #           内容...
        #           下一个字段
        
        pattern = rf"{prompt_name}:\s*\|(.+?)(?=\n\s*[a-z_]+:|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            raise ValueError(f"未找到Prompt: {prompt_name}")
        
        # 提取并清理文本
        text = match.group(1).strip()
        
        # 处理缩进
        lines = text.split("\n")
        if lines:
            # 检测第一行的缩进
            first_line = lines[0]
            indent = len(first_line) - len(first_line.lstrip())
            
            # 移除相同的缩进
            lines = [line[indent:] if line.startswith(" " * indent) else line for line in lines]
        
        return "\n".join(lines)
    
    def reload(self, filename: str):
        """重新加载指定文件的所有Prompt"""
        # 清除缓存中该文件的所有Prompt
        keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{filename}:")]
        for key in keys_to_remove:
            del self._cache[key]
        
        logger.info(f"清除Prompt缓存: {filename}")


# 全局便捷函数
_prompt_loader = PromptLoader()


def load_prompt(filename: str, prompt_name: str) -> str:
    """
    加载Prompt模板的便捷函数
    
    Args:
        filename: 文件名
        prompt_name: Prompt名称
        
    Returns:
        Prompt模板文本
    """
    return _prompt_loader.load(filename, prompt_name)