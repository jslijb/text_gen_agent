"""
选题生成模块

功能:
- 基于快手平台热点和对标账号数据生成热门选题
- 支持多种题材:都市言情、悬疑反转、家庭伦理、玄幻修真
- 符合快手平台规范的标题生成(17-30字)
"""

import logging
import re
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.model_manager import ModelManager
from app.config.prompts.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class TopicGenerator:
    """自动选题生成器"""
    
    def __init__(self):
        self.model_manager = ModelManager()
        self.llm = self.model_manager.get_model_for_role("topic_generator")
        self.prompt_template = load_prompt("video.yaml", "topic_generation")
    
    async def generate(self, project_id: str, hot_topics: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        生成选题
        
        Args:
            project_id: 项目ID
            hot_topics: 可选,热点话题列表
            
        Returns:
            选题信息
        """
        logger.info(f"开始生成选题: project_id={project_id}")
        
        # 构建Prompt
        prompt = self._build_prompt(hot_topics or [])
        
        # 调用LLM
        response = await self.llm.chat(prompt)
        
        # 解析响应
        result = self._parse_response(response)
        
        # 验证选题
        self._validate_topic(result)
        
        logger.info(f"选题生成完成: title={result.get('title')}")
        
        return result
    
    def _build_prompt(self, hot_topics: List[str]) -> str:
        """构建选题Prompt"""
        hot_topics_text = "\n".join(f"- {topic}" for topic in hot_topics[:5]) if hot_topics else "暂无热点话题"
        
        prompt = self.prompt_template.format(
            hot_topics=hot_topics_text,
            competitor_analysis=self._get_competitor_analysis()
        )
        
        return prompt
    
    def _get_competitor_analysis(self) -> str:
        """获取对标账号分析"""
        # 基于调研结果的对标账号信息
        return """- 漫剧工厂:都市言情、玄幻,动态漫风格,系列化内容,日更1-2条
- 短剧研究所:悬疑反转,强钩子开头,悬念结尾,日更
- AI小说推文:霸总甜宠,图文轮播,批量生产,日更3-5条
- 可灵AI创作营:科幻奇幻,纯AI生成,特效丰富,每周3-5条"""
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析选题响应"""
        try:
            # 尝试直接解析JSON
            data = json.loads(response)
            return data.get("topics", [data])[0]
        except json.JSONDecodeError:
            pass
        
        # 使用鲁棒解析器
        data = self._robust_json_parse(response)
        
        # 提取第一个选题
        topics = data.get("topics", [data])
        if topics:
            return topics[0]
        
        # 如果解析失败,生成默认选题
        logger.warning("选题解析失败,生成默认选题")
        return self._generate_default_topic()
    
    def _robust_json_parse(self, text: str) -> Dict[str, Any]:
        """鲁棒的JSON解析器"""
        # 清理控制字符
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        # 修复尾逗号
        text = re.sub(r',\s*([}\]])', r'\1', text)
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 提取JSON片段
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"无法解析JSON: {text[:100]}")
    
    def _validate_topic(self, topic: Dict[str, Any]) -> None:
        """验证选题"""
        # 检查标题长度
        title = topic.get("title", "")
        if len(title) < 17 or len(title) > 30:
            logger.warning(f"标题长度不符合规范: {len(title)} 字,标题: {title}")
        
        # 检查题材是否有效
        genre = topic.get("genre", "")
        valid_genres = ["都市言情", "悬疑反转", "家庭伦理", "玄幻修真"]
        if genre not in valid_genres:
            logger.warning(f"题材不在推荐列表中: {genre}")
        
        # 检查风格是否有效
        style = topic.get("style", "")
        valid_styles = ["comic", "realistic", "anime"]
        if style not in valid_styles:
            logger.warning(f"风格不在推荐列表中: {style}")
    
    def _generate_default_topic(self) -> Dict[str, Any]:
        """生成默认选题"""
        return {
            "title": "重生回19岁,她做了一个让所有人震惊的决定",
            "genre": "都市言情",
            "style": "comic",
            "target_duration": 30,
            "reason": "重生题材热度高,受众广,适合新号起步"
        }
    
    async def generate_multiple(self, project_id: str, count: int = 3, 
                                hot_topics: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        生成多个选题
        
        Args:
            project_id: 项目ID
            count: 选题数量
            hot_topics: 热点话题列表
            
        Returns:
            选题列表
        """
        topics = []
        
        for i in range(count):
            try:
                topic = await self.generate(project_id, hot_topics)
                topics.append(topic)
            except Exception as e:
                logger.error(f"生成第{i+1}个选题失败: {e}")
                # 如果生成失败,添加一个默认选题
                topics.append(self._generate_default_topic())
        
        return topics


class TopicValidator:
    """选题验证器"""
    
    @staticmethod
    def validate_title(title: str) -> Dict[str, Any]:
        """验证标题"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # 检查长度
        if len(title) < 17:
            result["warnings"].append(f"标题过短: {len(title)} 字,建议17-30字")
        elif len(title) > 30:
            result["warnings"].append(f"标题过长: {len(title)} 字,建议17-30字")
        
        # 检查是否包含悬念词
        suspense_words = ["真相揭晓", "意外发现", "结局反转", "竟然", "原来"]
        if not any(word in title for word in suspense_words):
            result["warnings"].append("标题缺少悬念词,建议添加悬念词提升吸引力")
        
        # 检查是否包含情绪词
        emotion_words = ["虐心", "高甜", "泪目", "震惊", "可怕"]
        if not any(word in title for word in emotion_words):
            result["warnings"].append("标题缺少情绪词,建议添加情绪词提升共鸣")
        
        # 检查是否包含题材词
        genre_words = ["重生", "穿越", "霸总", "复仇", "逆袭"]
        if not any(word in title for word in genre_words):
            result["warnings"].append("标题缺少题材词,建议添加题材词明确内容")
        
        # 检查是否有话题标签
        if "#" not in title:
            result["warnings"].append("标题缺少话题标签,建议添加#话题#提升曝光")
        
        return result
    
    @staticmethod
    def validate_genre(genre: str) -> bool:
        """验证题材"""
        valid_genres = ["都市言情", "悬疑反转", "家庭伦理", "玄幻修真"]
        return genre in valid_genres
    
    @staticmethod
    def validate_style(style: str) -> bool:
        """验证风格"""
        valid_styles = ["comic", "realistic", "anime"]
        return style in valid_styles


# Prompt加载器
import os

class PromptLoader:
    """Prompt模板加载器"""
    
    @staticmethod
    def load(filename: str, prompt_name: str) -> str:
        """加载Prompt模板"""
        prompt_dir = os.path.join(os.path.dirname(__file__), "prompts")
        filepath = os.path.join(prompt_dir, filename)
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Prompt文件不存在: {filepath}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 提取指定Prompt
        pattern = rf"{prompt_name}:\s*\|(.+?)\n\s*[A-Z]"
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        raise ValueError(f"未找到Prompt: {prompt_name}")


# 在模块加载时注册PromptLoader
def load_prompt(filename: str, prompt_name: str) -> str:
    """加载Prompt模板的便捷函数"""
    return PromptLoader.load(filename, prompt_name)