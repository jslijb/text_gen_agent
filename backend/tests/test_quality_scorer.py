"""
质量评分系统单元测试

测试内容:
1. 视频质量评分测试
2. 文案质量评分测试
3. 分镜质量评分测试
4. 素材质量评分测试
5. 质量检查测试
"""

import pytest
from datetime import datetime


class TestQualityScorer:
    """质量评分器测试"""
    
    def test_score_valid_video(self):
        """测试评分有效视频"""
        from app.services.quality_scorer import QualityScorer
        
        scorer = QualityScorer()
        
        result = scorer.score_video(
            "https://example.com/video.mp4",
            {"duration": 30, "resolution": "1080p"}
        )
        
        assert result is not None
        assert "score" in result
        assert "passed" in result
        assert "details" in result
    
    def test_score_invalid_video(self):
        """测试评分无效视频"""
        from app.services.quality_scorer import QualityScorer
        
        scorer = QualityScorer()
        
        result = scorer.score_video("")
        
        assert result["passed"] is False
        assert result["score"] < 100
    
    def test_score_valid_script(self):
        """测试评分有效文案"""
        from app.services.quality_scorer import QualityScorer
        
        scorer = QualityScorer()
        
        script = {
            "title": "重生回19岁,她做了一个让所有人震惊的决定#短剧#",
            "shots": [
                {
                    "sequence": 1,
                    "description": "女主角在教室里",
                    "narration": "震惊!重生回19岁,她做了一个决定...",
                    "image_prompt": "漫画风格,教室",
                    "video_prompt": "镜头推进"
                },
                {
                    "sequence": 2,
                    "description": "女主角特写",
                    "narration": "关注我,下集更精彩!",
                    "image_prompt": "漫画风格,特写",
                    "video_prompt": "镜头特写"
                }
            ]
        }
        
        result = scorer.score_script(script)
        
        assert result is not None
        assert "score" in result
        assert "passed" in result
    
    def test_score_short_title(self):
        """测试评分短标题"""
        from app.services.quality_scorer import QualityScorer
        
        scorer = QualityScorer()
        
        script = {
            "title": "短",
            "shots": []
        }
        
        result = scorer.score_script(script)
        
        assert result["score"] < 100
    
    def test_score_shot(self):
        """测试评分分镜"""
        from app.services.quality_scorer import QualityScorer
        
        scorer = QualityScorer()
        
        shot = {
            "sequence": 1,
            "description": "女主角在教室里",
            "narration": "重生回19岁",
            "duration": 5,
            "image_prompt": "漫画风格,教室",
            "video_prompt": "镜头推进"
        }
        
        result = scorer.score_shot(shot)
        
        assert result is not None
        assert "score" in result
        assert "passed" in result
    
    def test_score_shot_without_description(self):
        """测试评分缺少描述的分镜"""
        from app.services.quality_scorer import QualityScorer
        
        scorer = QualityScorer()
        
        shot = {
            "sequence": 1,
            "narration": "测试旁白"
        }
        
        result = scorer.score_shot(shot)
        
        assert result["score"] < 100
    
    def test_score_asset(self):
        """测试评分素材"""
        from app.services.quality_scorer import QualityScorer
        
        scorer = QualityScorer()
        
        asset = {
            "type": "character",
            "name": "女主角",
            "image_url": "https://example.com/image.png"
        }
        
        result = scorer.score_asset(asset)
        
        assert result is not None
        assert "score" in result
        assert "passed" in result
    
    def test_score_invalid_asset(self):
        """测试评分无效素材"""
        from app.services.quality_scorer import QualityScorer
        
        scorer = QualityScorer()
        
        asset = {}
        
        result = scorer.score_asset(asset)
        
        assert result["passed"] is False


class TestQualityChecker:
    """质量检查器测试"""
    
    @pytest.mark.asyncio
    async def test_check_and_retry_pass(self):
        """测试检查并重试(通过)"""
        from app.services.quality_scorer import QualityChecker
        
        checker = QualityChecker()
        
        script = {
            "title": "重生回19岁,她做了一个让所有人震惊的决定#短剧#",
            "shots": [
                {
                    "sequence": 1,
                    "description": "女主角在教室里",
                    "narration": "震惊!重生回19岁...",
                    "image_prompt": "漫画风格",
                    "video_prompt": "镜头推进"
                }
            ]
        }
        
        result = await checker.check_and_retry(
            script,
            "script",
            lambda: script
        )
        
        assert result is not None
        assert "passed" in result
    
    @pytest.mark.asyncio
    async def test_check_and_retry_fail(self):
        """测试检查并重试(失败)"""
        from app.services.quality_scorer import QualityChecker
        
        checker = QualityChecker()
        
        script = {
            "title": "短",
            "shots": []
        }
        
        result = await checker.check_and_retry(
            script,
            "script",
            lambda: script,
            max_retries=1
        )
        
        assert result is not None
        assert "passed" in result


class TestQualityReport:
    """质量报告测试"""
    
    def test_add_report(self):
        """测试添加报告"""
        from app.services.quality_scorer import QualityReport
        
        report = QualityReport()
        
        report.add_report({
            "score": 80,
            "passed": True,
            "type": "script"
        })
        
        summary = report.generate_summary()
        
        assert summary["total"] == 1
        assert summary["passed"] == 1
    
    def test_generate_summary(self):
        """测试生成摘要"""
        from app.services.quality_scorer import QualityReport
        
        report = QualityReport()
        
        # 添加多个报告
        report.add_report({"score": 90, "passed": True})
        report.add_report({"score": 80, "passed": True})
        report.add_report({"score": 60, "passed": False})
        
        summary = report.generate_summary()
        
        assert summary["total"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert "success_rate" in summary
        assert "average_score" in summary
    
    def test_empty_report(self):
        """测试空报告"""
        from app.services.quality_scorer import QualityReport
        
        report = QualityReport()
        
        summary = report.generate_summary()
        
        assert "error" in summary


# ============ 集成测试 ============

class TestQualityScorerIntegration:
    """质量评分集成测试"""
    
    @pytest.mark.integration
    def test_full_quality_check(self):
        """测试完整质量检查"""
        from app.services.quality_scorer import QualityScorer, QualityChecker
        
        scorer = QualityScorer()
        checker = QualityChecker()
        
        # 评分视频
        video_result = scorer.score_video("https://example.com/video.mp4")
        assert video_result is not None
        
        # 评分文案
        script_result = scorer.score_script({
            "title": "重生回19岁#短剧#",
            "shots": [{"sequence": 1, "description": "测试", "narration": "测试"}]
        })
        assert script_result is not None
        
        # 评分分镜
        shot_result = scorer.score_shot({
            "sequence": 1,
            "description": "测试",
            "narration": "测试",
            "duration": 5
        })
        assert shot_result is not None
        
        # 评分素材
        asset_result = scorer.score_asset({
            "type": "character",
            "name": "测试",
            "image_url": "https://example.com/image.png"
        })
        assert asset_result is not None


# ============ 性能测试 ============

class TestQualityScorerPerformance:
    """质量评分性能测试"""
    
    @pytest.mark.performance
    def test_score_script_performance(self):
        """测试评分文案性能"""
        import time
        from app.services.quality_scorer import QualityScorer
        
        scorer = QualityScorer()
        
        script = {
            "title": "重生回19岁#短剧#",
            "shots": [{"sequence": 1, "description": "测试", "narration": "测试"}]
        }
        
        start_time = time.time()
        
        for _ in range(100):
            scorer.score_script(script)
        
        elapsed = time.time() - start_time
        
        # 验证性能(100次应该在1秒内完成)
        assert elapsed < 1.0