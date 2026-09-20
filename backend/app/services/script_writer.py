"""
文案生成模块

功能:
- 根据选题生成适合AI漫剧的视频文案
- 符合快手平台规范(17-30字标题)
- 开头3秒钩子,结尾悬念引导
- 每5-10秒一个镜头切换
"""

import logging
import re
import json
from typing import Dict, Any, List, Optional

from app.services.model_manager import ModelManager
from app.config.prompts.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class ScriptWriter:
    """自动文案生成器"""
    
    def __init__(self):
        self.model_manager = ModelManager()
        self.llm = self.model_manager.get_model_for_role("script_writer")
        self.prompt_template = load_prompt("video.yaml", "script_generation")
    
    async def generate(self, project_id: str, topic: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成文案
        
        Args:
            project_id: 项目ID
            topic: 选题信息
            
        Returns:
            文案信息
        """
        logger.info(f"开始生成文案: project_id={project_id}, topic={topic.get('title')}")
        
        # 构建Prompt
        prompt = self._build_prompt(topic)
        
        # 调用LLM
        response = await self.llm.chat(prompt)
        
        # 解析响应
        result = self._parse_response(response)
        
        # 验证文案
        self._validate_script(result)
        
        logger.info(f"文案生成完成: title={result.get('title')}, shots={len(result.get('shots', []))}")
        
        return result
    
    def _build_prompt(self, topic: Dict[str, Any]) -> str:
        """构建文案Prompt"""
        prompt = self.prompt_template.format(
            topic=topic.get("title", ""),
            genre=topic.get("genre", ""),
            style=topic.get("style", ""),
            target_duration=topic.get("target_duration", 30)
        )
        
        return prompt
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析文案响应"""
        try:
            # 尝试直接解析JSON
            data = json.loads(response)
            return data
        except json.JSONDecodeError:
            pass
        
        # 使用鲁棒解析器
        data = self._robust_json_parse(response)
        
        # 确保有shots字段
        if "shots" not in data:
            data["shots"] = []
        
        return data
    
    def _robust_json_parse(self, text: str) -> Dict[str, Any]:
        """鲁棒的JSON解析器"""
        # 清理控制字符
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        # 修复尾逗号
        text = re.sub(r',\s*([}\]])', r'\1', text)
        
        # 修复中文引号
        text = text.replace('"', '"').replace('"', '"')
        
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
    
    def _validate_script(self, script: Dict[str, Any]) -> None:
        """验证文案"""
        # 检查标题长度
        title = script.get("title", "")
        if len(title) < 17 or len(title) > 30:
            logger.warning(f"标题长度不符合规范: {len(title)} 字")
        
        # 检查是否有分镜
        shots = script.get("shots", [])
        if not shots:
            logger.warning("文案没有分镜信息")
        
        # 检查分镜时长
        total_duration = sum(shot.get("duration", 0) for shot in shots)
        if total_duration == 0:
            logger.warning("总时长为0")
    
    def estimate_duration(self, script: Dict[str, Any]) -> int:
        """估算文案时长"""
        shots = script.get("shots", [])
        return sum(shot.get("duration", 0) for shot in shots)
    
    def extract_shots(self, script: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取分镜信息"""
        return script.get("shots", [])


class ScriptValidator:
    """文案验证器"""
    
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
            result["warnings"].append(f"标题过短: {len(title)} 字")
        elif len(title) > 30:
            result["warnings"].append(f"标题过长: {len(title)} 字")
        
        # 检查是否包含悬念词
        suspense_words = ["真相揭晓", "意外发现", "结局反转", "竟然", "原来"]
        if not any(word in title for word in suspense_words):
            result["warnings"].append("建议添加悬念词提升吸引力")
        
        # 检查是否包含情绪词
        emotion_words = ["虐心", "高甜", "泪目", "震惊", "可怕"]
        if not any(word in title for word in emotion_words):
            result["warnings"].append("建议添加情绪词提升共鸣")
        
        return result
    
    @staticmethod
    def validate_shots(shots: List[Dict[str, Any]]) -> Dict[str, Any]:
        """验证分镜"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        if not shots:
            result["errors"].append("分镜列表为空")
            result["valid"] = False
            return result
        
        # 检查每个分镜
        for i, shot in enumerate(shots):
            if "description" not in shot or not shot["description"]:
                result["warnings"].append(f"第{i+1}个分镜缺少描述")
            
            if "narration" not in shot or not shot["narration"]:
                result["warnings"].append(f"第{i+1}个分镜缺少旁白")
            
            duration = shot.get("duration", 0)
            if duration < 2 or duration > 10:
                result["warnings"].append(f"第{i+1}个分镜时长 {duration} 秒,建议2-10秒")
        
        return result
    
    @staticmethod
    def validate_duration(shots: List[Dict[str, Any]], target_duration: int) -> Dict[str, Any]:
        """验证时长"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        total_duration = sum(shot.get("duration", 0) for shot in shots)
        
        if total_duration == 0:
            result["errors"].append("总时长为0")
            result["valid"] = False
            return result
        
        # 允许±10%的误差
        min_duration = target_duration * 0.9
        max_duration = target_duration * 1.1
        
        if total_duration < min_duration:
            result["warnings"].append(f"总时长 {total_duration} 秒,低于目标 {target_duration} 秒")
        elif total_duration > max_duration:
            result["warnings"].append(f"总时长 {total_duration} 秒,超过目标 {target_duration} 秒")
        
        return result