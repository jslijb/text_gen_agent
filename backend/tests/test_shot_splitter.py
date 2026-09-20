"""
分镜拆分模块单元测试

测试内容:
1. Prompt加载测试
2. 分镜拆分测试
3. 分镜验证测试
4. JSON解析测试
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock


class TestShotSplitter:
    """分镜拆分器测试"""
    
    @pytest.fixture
    def mock_llm(self):
        """模拟LLM"""
        with patch('app.services.shot_splitter.ModelManager') as mock:
            mock_llm = Mock()
            mock_llm.chat.return_value = json.dumps({
                "shots": [
                    {
                        "sequence": 1,
                        "description": "女主角在教室里醒来",
                        "narration": "重生回19岁,看着熟悉的教室,她做了一个决定",
                        "duration": 5,
                        "image_prompt": "漫画风格,教室,阳光,高清",
                        "video_prompt": "镜头从窗外推进到教室内,流畅,30fps",
                        "transition": "淡入淡出"
                    },
                    {
                        "sequence": 2,
                        "description": "女主角坚定的表情",
                        "narration": "这一次,她不会再错过机会",
                        "duration": 5,
                        "image_prompt": "漫画风格,女主角特写,坚定的眼神,高清",
                        "video_prompt": "缓慢推进到女主角面部特写,流畅,30fps",
                        "transition": "切镜"
                    }
                ]
            })
            mock.return_value.get_model_for_role.return_value = mock_llm
            yield mock
    
    @pytest.mark.asyncio
    async def test_split_shots(self, mock_llm):
        """测试拆分分镜"""
        from app.services.shot_splitter import ShotSplitter
        
        splitter = ShotSplitter()
        script = {
            "content": "重生回19岁,她做了一个让所有人震惊的决定...",
            "target_duration": 30
        }
        shots = await splitter.split("test-project-id", script)
        
        assert len(shots) == 2
        assert shots[0]["sequence"] == 1
        assert shots[1]["sequence"] == 2
    
    @pytest.mark.asyncio
    async def test_calculate_total_duration(self, mock_llm):
        """测试计算总时长"""
        from app.services.shot_splitter import ShotSplitter
        
        splitter = ShotSplitter()
        script = {
            "content": "测试内容",
            "target_duration": 30
        }
        shots = await splitter.split("test-project-id", script)
        
        duration = splitter.calculate_total_duration(shots)
        assert duration == 10  # 5 + 5
    
    @pytest.mark.asyncio
    async def test_adjust_durations(self, mock_llm):
        """测试调整分镜时长"""
        from app.services.shot_splitter import ShotSplitter
        
        splitter = ShotSplitter()
        script = {
            "content": "测试内容",
            "target_duration": 30
        }
        shots = await splitter.split("test-project-id", script)
        
        # 调整到20秒
        adjusted_shots = splitter.adjust_durations(shots, 20)
        
        new_duration = splitter.calculate_total_duration(adjusted_shots)
        assert new_duration == 20
    
    def test_robust_json_parse_valid(self):
        """测试JSON解析(有效JSON)"""
        from app.services.shot_splitter import ShotSplitter
        
        splitter = ShotSplitter()
        text = '{"shots": [{"sequence": 1, "duration": 5}]}'
        result = splitter._robust_json_parse(text)
        
        assert "shots" in result
        assert len(result["shots"]) == 1
    
    def test_robust_json_parse_with_trailing_comma(self):
        """测试JSON解析(包含尾逗号)"""
        from app.services.shot_splitter import ShotSplitter
        
        splitter = ShotSplitter()
        text = '{"shots": [{"sequence": 1, "duration": 5},]}'
        result = splitter._robust_json_parse(text)
        
        assert "shots" in result


class TestShotOptimizer:
    """分镜优化器测试"""
    
    def test_optimize_sequence(self):
        """测试优化分镜顺序"""
        from app.services.shot_splitter import ShotOptimizer
        
        shots = [
            {"sequence": 3, "description": "第三个分镜"},
            {"sequence": 1, "description": "第一个分镜"},
            {"sequence": 2, "description": "第二个分镜"}
        ]
        
        optimized = ShotOptimizer.optimize_sequence(shots)
        
        assert optimized[0]["sequence"] == 1
        assert optimized[1]["sequence"] == 2
        assert optimized[2]["sequence"] == 3
    
    def test_optimize_transitions(self):
        """测试优化转场"""
        from app.services.shot_splitter import ShotOptimizer
        
        shots = [
            {"sequence": 1, "description": "第一个分镜"},
            {"sequence": 2, "description": "第二个分镜", "transition": "缩放"},
            {"sequence": 3, "description": "第三个分镜"}
        ]
        
        optimized = ShotOptimizer.optimize_transitions(shots)
        
        assert optimized[0]["transition"] == "淡入淡出"
        assert optimized[1]["transition"] == "缩放"
        assert optimized[2]["transition"] == "淡入淡出"
    
    def test_optimize_durations(self):
        """测试优化分镜时长"""
        from app.services.shot_splitter import ShotOptimizer
        
        shots = [
            {"sequence": 1, "duration": 5},
            {"sequence": 2, "duration": 5}
        ]
        
        optimized = ShotOptimizer.optimize_durations(shots, 10)
        
        assert sum(shot["duration"] for shot in optimized) == 10


class TestShotQualityChecker:
    """分镜质量检查器测试"""
    
    def test_check_valid_shot(self):
        """测试检查有效分镜"""
        from app.services.shot_splitter import ShotQualityChecker
        
        shot = {
            "description": "测试描述",
            "narration": "测试旁白",
            "duration": 5,
            "image_prompt": "测试图像提示词",
            "video_prompt": "测试视频提示词"
        }
        
        result = ShotQualityChecker.check_shot(shot)
        
        assert result["valid"] is True
        assert result["score"] == 100
    
    def test_check_invalid_shot(self):
        """测试检查无效分镜"""
        from app.services.shot_splitter import ShotQualityChecker
        
        shot = {}
        
        result = ShotQualityChecker.check_shot(shot)
        
        assert result["valid"] is False
        assert result["score"] < 100
    
    def test_check_shots(self):
        """测试检查分镜列表"""
        from app.services.shot_splitter import ShotQualityChecker
        
        shots = [
            {
                "description": "测试描述1",
                "narration": "测试旁白1",
                "duration": 5,
                "image_prompt": "测试图像提示词1",
                "video_prompt": "测试视频提示词1"
            },
            {
                "description": "测试描述2",
                "narration": "测试旁白2",
                "duration": 5,
                "image_prompt": "测试图像提示词2",
                "video_prompt": "测试视频提示词2"
            }
        ]
        
        result = ShotQualityChecker.check_shots(shots)
        
        assert result["valid"] is True
        assert result["average_score"] == 100
    
    def test_check_empty_shots(self):
        """测试检查空分镜列表"""
        from app.services.shot_splitter import ShotQualityChecker
        
        result = ShotQualityChecker.check_shots([])
        
        assert result["valid"] is False


# ============ 集成测试 ============

class TestShotSplitterIntegration:
    """分镜拆分集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_shot_splitting(self):
        """测试完整分镜拆分流程"""
        from app.services.shot_splitter import ShotSplitter
        
        splitter = ShotSplitter()
        
        # 拆分分镜
        script = {
            "content": "重生回19岁,她做了一个让所有人震惊的决定。这一次,她不会再错过机会。",
            "target_duration": 30
        }
        shots = await splitter.split("test-project-id", script)
        
        # 验证
        assert shots is not None
        assert len(shots) > 0
        
        # 验证每个分镜
        for i, shot in enumerate(shots):
            assert "sequence" in shot
            assert "description" in shot
            assert "narration" in shot
            assert "duration" in shot
            assert 2 <= shot["duration"] <= 10