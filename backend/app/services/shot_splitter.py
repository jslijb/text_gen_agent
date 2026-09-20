"""
分镜拆分模块

功能:
- 将文案拆分为具体镜头
- 每个镜头2-5秒
- 支持动态镜头和转场
- 生成图像和视频提示词
"""

import logging
import re
import json
from typing import Dict, Any, List, Optional

from app.services.model_manager import ModelManager
from app.config.prompts.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class ShotSplitter:
    """自动分镜拆分器"""
    
    def __init__(self):
        self.model_manager = ModelManager()
        self.llm = self.model_manager.get_model_for_role("shot_splitter")
        self.prompt_template = load_prompt("video.yaml", "shot_splitting")
    
    async def split(self, project_id: str, script: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        拆分分镜
        
        Args:
            project_id: 项目ID
            script: 文案信息
            
        Returns:
            分镜列表
        """
        logger.info(f"开始拆分分镜: project_id={project_id}")
        
        # 构建Prompt
        prompt = self._build_prompt(script)
        
        # 调用LLM
        response = await self.llm.chat(prompt)
        
        # 解析响应
        shots = self._parse_response(response)
        
        # 验证分镜
        self._validate_shots(shots)
        
        # 为每个分镜生成提示词
        for i, shot in enumerate(shots):
            if "image_prompt" not in shot or not shot["image_prompt"]:
                shot["image_prompt"] = self._generate_image_prompt(shot)
            if "video_prompt" not in shot or not shot["video_prompt"]:
                shot["video_prompt"] = self._generate_video_prompt(shot)
            shot["sequence"] = i + 1
        
        logger.info(f"分镜拆分完成: shots={len(shots)}")
        
        return shots
    
    def _build_prompt(self, script: Dict[str, Any]) -> str:
        """构建分镜Prompt"""
        prompt = self.prompt_template.format(
            script=script.get("content", ""),
            target_duration=script.get("target_duration", 30)
        )
        
        return prompt
    
    def _parse_response(self, response: str) -> List[Dict[str, Any]]:
        """解析分镜响应"""
        try:
            # 尝试直接解析JSON
            data = json.loads(response)
            return data.get("shots", [])
        except json.JSONDecodeError:
            pass
        
        # 使用鲁棒解析器
        data = self._robust_json_parse(response)
        
        # 提取分镜列表
        shots = data.get("shots", [])
        
        # 如果没有shots字段,尝试从其他字段提取
        if not shots:
            # 尝试从data中提取
            for key in ["shots", "scenes", "clips"]:
                if key in data and isinstance(data[key], list):
                    shots = data[key]
                    break
        
        return shots
    
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
    
    def _validate_shots(self, shots: List[Dict[str, Any]]) -> None:
        """验证分镜"""
        if not shots:
            logger.warning("分镜列表为空")
            return
        
        for i, shot in enumerate(shots):
            # 检查时长
            duration = shot.get("duration", 0)
            if duration < 2 or duration > 10:
                logger.warning(f"第{i+1}个分镜时长 {duration} 秒,建议2-10秒")
            
            # 检查描述
            if "description" not in shot or not shot["description"]:
                logger.warning(f"第{i+1}个分镜缺少描述")
            
            # 检查旁白
            if "narration" not in shot or not shot["narration"]:
                logger.warning(f"第{i+1}个分镜缺少旁白")
    
    def _generate_image_prompt(self, shot: Dict[str, Any]) -> str:
        """生成图像提示词"""
        description = shot.get("description", "")
        
        # 构建基础提示词
        prompt = f"漫画风格,{description},高清,细节丰富,8k"
        
        return prompt
    
    def _generate_video_prompt(self, shot: Dict[str, Any]) -> str:
        """生成视频提示词"""
        description = shot.get("description", "")
        transition = shot.get("transition", "切镜")
        
        # 构建基础提示词
        prompt = f"{description},"
        
        # 添加镜头运动
        if "特写" in description:
            prompt += "缓慢推进,"
        elif "远景" in description:
            prompt += "缓慢拉远,"
        else:
            prompt += "轻微平移,"
        
        # 添加转场
        if transition == "淡入淡出":
            prompt += "淡入淡出转场,"
        elif transition == "缩放":
            prompt += "缩放转场,"
        else:
            prompt += "硬切转场,"
        
        prompt += "流畅,30fps"
        
        return prompt
    
    def calculate_total_duration(self, shots: List[Dict[str, Any]]) -> int:
        """计算总时长"""
        return sum(shot.get("duration", 0) for shot in shots)
    
    def adjust_durations(self, shots: List[Dict[str, Any]], target_duration: int) -> List[Dict[str, Any]]:
        """调整分镜时长以匹配目标时长"""
        current_duration = self.calculate_total_duration(shots)
        
        if current_duration == 0:
            return shots
        
        # 计算调整比例
        ratio = target_duration / current_duration
        
        # 调整每个分镜的时长
        for shot in shots:
            original_duration = shot.get("duration", 5)
            new_duration = max(2, min(10, int(original_duration * ratio)))
            shot["duration"] = new_duration
        
        return shots


class ShotOptimizer:
    """分镜优化器"""
    
    @staticmethod
    def optimize_sequence(shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """优化分镜顺序"""
        # 确保分镜按sequence排序
        return sorted(shots, key=lambda x: x.get("sequence", 0))
    
    @staticmethod
    def optimize_transitions(shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """优化转场"""
        for i, shot in enumerate(shots):
            if "transition" not in shot or not shot["transition"]:
                # 根据内容自动选择转场
                if i == 0:
                    shot["transition"] = "淡入淡出"
                elif i == len(shots) - 1:
                    shot["transition"] = "淡入淡出"
                else:
                    shot["transition"] = "切镜"
        
        return shots
    
    @staticmethod
    def optimize_durations(shots: List[Dict[str, Any]], target_duration: int) -> List[Dict[str, Any]]:
        """优化分镜时长"""
        current_duration = sum(shot.get("duration", 0) for shot in shots)
        
        if current_duration == 0:
            return shots
        
        # 计算调整比例
        ratio = target_duration / current_duration
        
        # 调整每个分镜的时长
        for shot in shots:
            original_duration = shot.get("duration", 5)
            new_duration = max(2, min(10, int(original_duration * ratio)))
            shot["duration"] = new_duration
        
        return shots


class ShotQualityChecker:
    """分镜质量检查器"""
    
    @staticmethod
    def check_shot(shot: Dict[str, Any]) -> Dict[str, Any]:
        """检查分镜质量"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "score": 100
        }
        
        # 检查描述
        if "description" not in shot or not shot["description"]:
            result["errors"].append("缺少描述")
            result["valid"] = False
            result["score"] -= 30
        
        # 检查旁白
        if "narration" not in shot or not shot["narration"]:
            result["warnings"].append("缺少旁白")
            result["score"] -= 10
        
        # 检查时长
        duration = shot.get("duration", 0)
        if duration < 2:
            result["warnings"].append(f"时长过短: {duration} 秒")
            result["score"] -= 10
        elif duration > 10:
            result["warnings"].append(f"时长过长: {duration} 秒")
            result["score"] -= 10
        
        # 检查图像提示词
        if "image_prompt" not in shot or not shot["image_prompt"]:
            result["warnings"].append("缺少图像提示词")
            result["score"] -= 10
        
        # 检查视频提示词
        if "video_prompt" not in shot or not shot["video_prompt"]:
            result["warnings"].append("缺少视频提示词")
            result["score"] -= 10
        
        return result
    
    @staticmethod
    def check_shots(shots: List[Dict[str, Any]]) -> Dict[str, Any]:
        """检查分镜列表质量"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "total_score": 0,
            "average_score": 0
        }
        
        if not shots:
            result["errors"].append("分镜列表为空")
            result["valid"] = False
            return result
        
        # 检查每个分镜
        total_score = 0
        for i, shot in enumerate(shots):
            shot_result = ShotQualityChecker.check_shot(shot)
            total_score += shot_result["score"]
            
            if not shot_result["valid"]:
                result["errors"].append(f"第{i+1}个分镜: {shot_result['errors']}")
            
            result["warnings"].extend([f"第{i+1}个分镜: {w}" for w in shot_result["warnings"]])
        
        result["total_score"] = total_score
        result["average_score"] = total_score / len(shots)
        
        if result["average_score"] < 60:
            result["valid"] = False
        
        return result