"""
质量评分系统

功能:
- 视频质量评分
- 文案质量评分
- 分镜质量评分
- 素材质量评分
- 低质量重试机制
"""

import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class QualityScorer:
    """质量评分器"""
    
    def __init__(self):
        # 评分阈值
        self.thresholds = {
            "video": 70,
            "script": 75,
            "shot": 80,
            "asset": 85
        }
    
    def score_video(self, video_url: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        评分视频质量
        
        Args:
            video_url: 视频URL
            metadata: 视频元数据
            
        Returns:
            评分结果
        """
        score = 100
        details = []
        
        # 检查URL有效性
        if not video_url or not video_url.startswith("http"):
            score -= 30
            details.append({"item": "URL有效性", "score": 0, "note": "无效的视频URL"})
        else:
            details.append({"item": "URL有效性", "score": 100, "note": "有效"})
        
        # 检查视频时长(如果有元数据)
        if metadata and "duration" in metadata:
            duration = metadata["duration"]
            if 15 <= duration <= 60:
                details.append({"item": "时长", "score": 100, "note": f"{duration}秒,符合规范"})
            else:
                score -= 10
                details.append({"item": "时长", "score": 80, "note": f"{duration}秒,建议15-60秒"})
        
        # 检查视频分辨率
        if metadata and "resolution" in metadata:
            resolution = metadata["resolution"]
            if resolution in ["720p", "1080p"]:
                details.append({"item": "分辨率", "score": 100, "note": f"{resolution},符合规范"})
            else:
                score -= 5
                details.append({"item": "分辨率", "score": 90, "note": f"{resolution},建议720p或1080p"})
        
        # 综合评分
        total_score = sum(d["score"] for d in details) / len(details) if details else 0
        
        result = {
            "score": total_score,
            "threshold": self.thresholds["video"],
            "passed": total_score >= self.thresholds["video"],
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"视频质量评分: {total_score}, 通过: {result['passed']}")
        
        return result
    
    def score_script(self, script: Dict[str, Any]) -> Dict[str, Any]:
        """评分文案质量"""
        score = 100
        details = []
        
        # 检查标题
        title = script.get("title", "")
        title_length = len(title)
        
        if 17 <= title_length <= 30:
            details.append({"item": "标题长度", "score": 100, "note": f"{title_length}字,符合规范"})
        else:
            score -= 10
            details.append({"item": "标题长度", "score": 80, "note": f"{title_length}字,建议17-30字"})
        
        # 检查标题是否包含悬念词
        suspense_words = ["真相揭晓", "意外发现", "结局反转", "竟然", "原来"]
        if any(word in title for word in suspense_words):
            details.append({"item": "悬念词", "score": 100, "note": "包含悬念词"})
        else:
            score -= 5
            details.append({"item": "悬念词", "score": 90, "note": "建议添加悬念词"})
        
        # 检查标题是否包含情绪词
        emotion_words = ["虐心", "高甜", "泪目", "震惊", "可怕"]
        if any(word in title for word in emotion_words):
            details.append({"item": "情绪词", "score": 100, "note": "包含情绪词"})
        else:
            score -= 5
            details.append({"item": "情绪词", "score": 90, "note": "建议添加情绪词"})
        
        # 检查是否有分镜
        shots = script.get("shots", [])
        if shots:
            details.append({"item": "分镜", "score": 100, "note": f"{len(shots)}个分镜"})
        else:
            score -= 20
            details.append({"item": "分镜", "score": 60, "note": "缺少分镜"})
        
        # 检查开头钩子
        if shots and shots[0].get("narration"):
            narration = shots[0]["narration"]
            hook_words = ["震惊", "意外", "竟然", "真相", "原来"]
            if any(word in narration[:20] for word in hook_words):
                details.append({"item": "开头钩子", "score": 100, "note": "开头有钩子"})
            else:
                score -= 5
                details.append({"item": "开头钩子", "score": 90, "note": "建议开头添加钩子"})
        
        # 检查结尾悬念
        if shots and shots[-1].get("narration"):
            narration = shots[-1]["narration"]
            suspense_end = ["下集", "续集", "未完", "待续", "关注"]
            if any(word in narration[-20:] for word in suspense_end):
                details.append({"item": "结尾悬念", "score": 100, "note": "结尾有悬念"})
            else:
                score -= 5
                details.append({"item": "结尾悬念", "score": 90, "note": "建议结尾添加悬念"})
        
        # 综合评分
        total_score = sum(d["score"] for d in details) / len(details) if details else 0
        
        result = {
            "score": total_score,
            "threshold": self.thresholds["script"],
            "passed": total_score >= self.thresholds["script"],
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"文案质量评分: {total_score}, 通过: {result['passed']}")
        
        return result
    
    def score_shot(self, shot: Dict[str, Any]) -> Dict[str, Any]:
        """评分分镜质量"""
        score = 100
        details = []
        
        # 检查描述
        if shot.get("description"):
            details.append({"item": "描述", "score": 100, "note": "有描述"})
        else:
            score -= 20
            details.append({"item": "描述", "score": 60, "note": "缺少描述"})
        
        # 检查旁白
        if shot.get("narration"):
            details.append({"item": "旁白", "score": 100, "note": "有旁白"})
        else:
            score -= 15
            details.append({"item": "旁白", "score": 70, "note": "缺少旁白"})
        
        # 检查时长
        duration = shot.get("duration", 0)
        if 2 <= duration <= 10:
            details.append({"item": "时长", "score": 100, "note": f"{duration}秒,符合规范"})
        else:
            score -= 10
            details.append({"item": "时长", "score": 80, "note": f"{duration}秒,建议2-10秒"})
        
        # 检查图像提示词
        if shot.get("image_prompt"):
            details.append({"item": "图像提示词", "score": 100, "note": "有图像提示词"})
        else:
            score -= 10
            details.append({"item": "图像提示词", "score": 80, "note": "缺少图像提示词"})
        
        # 检查视频提示词
        if shot.get("video_prompt"):
            details.append({"item": "视频提示词", "score": 100, "note": "有视频提示词"})
        else:
            score -= 10
            details.append({"item": "视频提示词", "score": 80, "note": "缺少视频提示词"})
        
        # 综合评分
        total_score = sum(d["score"] for d in details) / len(details) if details else 0
        
        result = {
            "score": total_score,
            "threshold": self.thresholds["shot"],
            "passed": total_score >= self.thresholds["shot"],
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return result
    
    def score_asset(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        """评分素材质量"""
        score = 100
        details = []
        
        # 检查类型
        if asset.get("type"):
            details.append({"item": "类型", "score": 100, "note": asset["type"]})
        else:
            score -= 20
            details.append({"item": "类型", "score": 60, "note": "缺少类型"})
        
        # 检查图像URL
        if asset.get("image_url") and asset["image_url"].startswith("http"):
            details.append({"item": "图像URL", "score": 100, "note": "有效"})
        else:
            score -= 30
            details.append({"item": "图像URL", "score": 40, "note": "无效的图像URL"})
        
        # 检查名称
        if asset.get("name"):
            details.append({"item": "名称", "score": 100, "note": asset["name"]})
        else:
            score -= 5
            details.append({"item": "名称", "score": 90, "note": "缺少名称"})
        
        # 综合评分
        total_score = sum(d["score"] for d in details) / len(details) if details else 0
        
        result = {
            "score": total_score,
            "threshold": self.thresholds["asset"],
            "passed": total_score >= self.thresholds["asset"],
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return result


class QualityChecker:
    """质量检查器"""
    
    def __init__(self):
        self.scorer = QualityScorer()
    
    async def check_and_retry(
        self, 
        item: Dict[str, Any], 
        item_type: str,
        retry_func: callable,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        检查质量并重试
        
        Args:
            item: 待检查项
            item_type: 类型(video/script/shot/asset)
            retry_func: 重试函数
            max_retries: 最大重试次数
            
        Returns:
            检查结果
        """
        for attempt in range(max_retries):
            # 评分
            if item_type == "video":
                result = self.scorer.score_video(item.get("url"), item.get("metadata"))
            elif item_type == "script":
                result = self.scorer.score_script(item)
            elif item_type == "shot":
                result = self.scorer.score_shot(item)
            elif item_type == "asset":
                result = self.scorer.score_asset(item)
            else:
                raise ValueError(f"未知类型: {item_type}")
            
            # 如果通过,返回结果
            if result["passed"]:
                logger.info(f"质量检查通过: {item_type}, 分数: {result['score']}")
                return {
                    "passed": True,
                    "attempt": attempt + 1,
                    "result": result
                }
            
            # 如果未通过,重试
            logger.warning(f"质量检查未通过: {item_type}, 分数: {result['score']}, 尝试: {attempt+1}/{max_retries}")
            
            if attempt < max_retries - 1:
                # 执行重试
                try:
                    item = await retry_func()
                except Exception as e:
                    logger.error(f"重试失败: {e}")
        
        # 超过最大重试次数
        logger.error(f"质量检查失败,超过最大重试次数: {max_retries}")
        
        return {
            "passed": False,
            "attempt": max_retries,
            "result": result
        }


class QualityReport:
    """质量报告"""
    
    def __init__(self):
        self.reports: List[Dict[str, Any]] = []
    
    def add_report(self, report: Dict[str, Any]):
        """添加报告"""
        self.reports.append(report)
    
    def generate_summary(self) -> Dict[str, Any]:
        """生成摘要"""
        if not self.reports:
            return {"error": "没有报告"}
        
        total = len(self.reports)
        passed = sum(1 for r in self.reports if r.get("passed"))
        failed = total - passed
        
        avg_score = sum(r.get("score", 0) for r in self.reports) / total
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": f"{passed/total*100:.1f}%",
            "average_score": f"{avg_score:.1f}",
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def export_report(self, filepath: str):
        """导出报告"""
        import json
        
        summary = self.generate_summary()
        
        report = {
            "summary": summary,
            "details": self.reports
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"报告已导出: {filepath}")