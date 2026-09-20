"""
文案生成模块单元测试

测试内容:
1. Prompt加载测试
2. 文案生成测试
3. 文案验证测试
4. JSON解析测试
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock


class TestScriptWriter:
    """文案生成器测试"""
    
    @pytest.fixture
    def mock_llm(self):
        """模拟LLM"""
        with patch('app.services.script_writer.ModelManager') as mock:
            mock_llm = Mock()
            mock_llm.chat.return_value = json.dumps({
                "title": "重生回19岁,她做了一个让所有人震惊的决定",
                "content": "完整的文案内容...",
                "shots": [
                    {
                        "sequence": 1,
                        "description": "女主角在教室里醒来",
                        "narration": "重生回19岁,看着熟悉的教室,她做了一个决定",
                        "duration": 5,
                        "image_prompt": "漫画风格,教室,阳光",
                        "video_prompt": "镜头从窗外推进到教室内",
                        "transition": "淡入淡出"
                    },
                    {
                        "sequence": 2,
                        "description": "女主角坚定的表情",
                        "narration": "这一次,她不会再错过机会",
                        "duration": 5,
                        "image_prompt": "漫画风格,女主角特写,坚定的眼神",
                        "video_prompt": "缓慢推进到女主角面部特写",
                        "transition": "切镜"
                    }
                ]
            })
            mock.return_value.get_model_for_role.return_value = mock_llm
            yield mock
    
    @pytest.mark.asyncio
    async def test_generate_script(self, mock_llm):
        """测试生成文案"""
        from app.services.script_writer import ScriptWriter
        
        writer = ScriptWriter()
        topic = {
            "title": "重生回19岁",
            "genre": "都市言情",
            "style": "comic",
            "target_duration": 30
        }
        result = await writer.generate("test-project-id", topic)
        
        assert "title" in result
        assert "content" in result
        assert "shots" in result
        assert len(result["shots"]) == 2
    
    @pytest.mark.asyncio
    async def test_estimate_duration(self, mock_llm):
        """测试估算时长"""
        from app.services.script_writer import ScriptWriter
        
        writer = ScriptWriter()
        topic = {
            "title": "重生回19岁",
            "genre": "都市言情",
            "style": "comic",
            "target_duration": 30
        }
        script = await writer.generate("test-project-id", topic)
        
        duration = writer.estimate_duration(script)
        assert duration == 10  # 5 + 5
    
    def test_robust_json_parse_valid(self):
        """测试JSON解析(有效JSON)"""
        from app.services.script_writer import ScriptWriter
        
        writer = ScriptWriter()
        text = '{"title": "测试", "shots": []}'
        result = writer._robust_json_parse(text)
        
        assert result["title"] == "测试"
        assert result["shots"] == []
    
    def test_robust_json_parse_with_control_chars(self):
        """测试JSON解析(包含控制字符)"""
        from app.services.script_writer import ScriptWriter
        
        writer = ScriptWriter()
        text = '{\x00"title": "测试\x01"}'
        result = writer._robust_json_parse(text)
        
        assert result["title"] == "测试"
    
    def test_robust_json_parse_with_trailing_comma(self):
        """测试JSON解析(包含尾逗号)"""
        from app.services.script_writer import ScriptWriter
        
        writer = ScriptWriter()
        text = '{"title": "测试",}'
        result = writer._robust_json_parse(text)
        
        assert result["title"] == "测试"


class TestScriptValidator:
    """文案验证器测试"""
    
    def test_validate_valid_title(self):
        """测试验证有效标题"""
        from app.services.script_writer import ScriptValidator
        
        validator = ScriptValidator()
        result = validator.validate_title("重生回19岁,她做了一个让所有人震惊的决定#短剧#")
        
        assert result["valid"] is True
    
    def test_validate_short_title(self):
        """测试验证过短标题"""
        from app.services.script_writer import ScriptValidator
        
        validator = ScriptValidator()
        result = validator.validate_title("短标题")
        
        assert result["valid"] is True
        assert any("过短" in w for w in result["warnings"])
    
    def test_validate_valid_shots(self):
        """测试验证有效分镜"""
        from app.services.script_writer import ScriptValidator
        
        validator = ScriptValidator()
        shots = [
            {
                "sequence": 1,
                "description": "测试描述",
                "narration": "测试旁白",
                "duration": 5
            }
        ]
        result = validator.validate_shots(shots)
        
        assert result["valid"] is True
    
    def test_validate_empty_shots(self):
        """测试验证空分镜"""
        from app.services.script_writer import ScriptValidator
        
        validator = ScriptValidator()
        result = validator.validate_shots([])
        
        assert result["valid"] is False
        assert any("为空" in e for e in result["errors"])
    
    def test_validate_shot_duration(self):
        """测试验证分镜时长"""
        from app.services.script_writer import ScriptValidator
        
        validator = ScriptValidator()
        shots = [
            {
                "sequence": 1,
                "description": "测试",
                "narration": "测试",
                "duration": 1  # 过短
            },
            {
                "sequence": 2,
                "description": "测试",
                "narration": "测试",
                "duration": 15  # 过长
            }
        ]
        result = validator.validate_shots(shots)
        
        assert result["valid"] is True
        assert len(result["warnings"]) >= 2
    
    def test_validate_duration(self):
        """测试验证时长"""
        from app.services.script_writer import ScriptValidator
        
        validator = ScriptValidator()
        shots = [{"duration": 5}, {"duration": 5}]
        result = validator.validate_duration(shots, target_duration=10)
        
        assert result["valid"] is True
    
    def test_validate_duration_mismatch(self):
        """测试验证时长不匹配"""
        from app.services.script_writer import ScriptValidator
        
        validator = ScriptValidator()
        shots = [{"duration": 5}]
        result = validator.validate_duration(shots, target_duration=20)
        
        assert result["valid"] is True
        assert len(result["warnings"]) > 0


# ============ 集成测试 ============

class TestScriptWriterIntegration:
    """文案生成集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_script_generation(self):
        """测试完整文案生成流程"""
        from app.services.script_writer import ScriptWriter
        
        writer = ScriptWriter()
        
        # 生成文案
        topic = {
            "title": "重生回19岁",
            "genre": "都市言情",
            "style": "comic",
            "target_duration": 30
        }
        script = await writer.generate("test-project-id", topic)
        
        # 验证
        assert script is not None
        assert "title" in script
        assert "shots" in script
        
        # 验证标题长度
        title_length = len(script["title"])
        assert 15 <= title_length <= 35, f"标题长度 {title_length} 不在推荐范围内"