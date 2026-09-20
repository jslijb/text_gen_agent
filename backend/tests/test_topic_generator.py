"""
选题生成模块单元测试

测试内容:
1. Prompt加载测试
2. 选题生成测试
3. 选题验证测试
4. JSON解析测试
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock


class TestPromptLoader:
    """Prompt加载器测试"""
    
    def test_load_prompt(self):
        """测试加载Prompt"""
        from app.config.prompts.prompt_loader import load_prompt
        
        prompt = load_prompt("video.yaml", "topic_generation")
        
        assert prompt is not None
        assert len(prompt) > 0
        assert "快手AI漫剧选题专家" in prompt
    
    def test_load_nonexistent_prompt(self):
        """测试加载不存在的Prompt"""
        from app.config.prompts.prompt_loader import load_prompt
        
        with pytest.raises(ValueError):
            load_prompt("video.yaml", "nonexistent_prompt")
    
    def test_prompt_caching(self):
        """测试Prompt缓存"""
        from app.config.prompts.prompt_loader import PromptLoader
        
        loader = PromptLoader()
        prompt1 = loader.load("video.yaml", "topic_generation")
        prompt2 = loader.load("video.yaml", "topic_generation")
        
        assert prompt1 == prompt2


class TestTopicGenerator:
    """选题生成器测试"""
    
    @pytest.fixture
    def mock_llm(self):
        """模拟LLM"""
        with patch('app.services.topic_generator.ModelManager') as mock:
            mock_llm = Mock()
            mock_llm.chat.return_value = json.dumps({
                "topics": [{
                    "title": "重生回19岁,她做了一个让所有人震惊的决定",
                    "genre": "都市言情",
                    "style": "comic",
                    "target_duration": 30,
                    "reason": "重生题材热度高"
                }]
            })
            mock.return_value.get_model_for_role.return_value = mock_llm
            yield mock
    
    @pytest.mark.asyncio
    async def test_generate_topic(self, mock_llm):
        """测试生成选题"""
        from app.services.topic_generator import TopicGenerator
        
        generator = TopicGenerator()
        result = await generator.generate("test-project-id")
        
        assert "title" in result
        assert "genre" in result
        assert "style" in result
        assert result["title"] is not None
    
    @pytest.mark.asyncio
    async def test_generate_multiple_topics(self, mock_llm):
        """测试生成多个选题"""
        from app.services.topic_generator import TopicGenerator
        
        generator = TopicGenerator()
        topics = await generator.generate_multiple("test-project-id", count=3)
        
        assert len(topics) == 3
        for topic in topics:
            assert "title" in topic
    
    def test_robust_json_parse_valid(self):
        """测试JSON解析(有效JSON)"""
        from app.services.topic_generator import TopicGenerator
        
        generator = TopicGenerator()
        text = '{"title": "测试", "genre": "都市言情"}'
        result = generator._robust_json_parse(text)
        
        assert result["title"] == "测试"
        assert result["genre"] == "都市言情"
    
    def test_robust_json_parse_with_control_chars(self):
        """测试JSON解析(包含控制字符)"""
        from app.services.topic_generator import TopicGenerator
        
        generator = TopicGenerator()
        text = '{\x00"title": "测试\x01"}'
        result = generator._robust_json_parse(text)
        
        assert result["title"] == "测试"
    
    def test_robust_json_parse_with_trailing_comma(self):
        """测试JSON解析(包含尾逗号)"""
        from app.services.topic_generator import TopicGenerator
        
        generator = TopicGenerator()
        text = '{"title": "测试",}'
        result = generator._robust_json_parse(text)
        
        assert result["title"] == "测试"


class TestTopicValidator:
    """选题验证器测试"""
    
    def test_validate_valid_title(self):
        """测试验证有效标题"""
        from app.services.topic_generator import TopicValidator
        
        validator = TopicValidator()
        result = validator.validate_title("重生回19岁,她做了一个让所有人震惊的决定#短剧#")
        
        assert result["valid"] is True
        assert len(result["warnings"]) > 0  # 可能有警告
    
    def test_validate_short_title(self):
        """测试验证过短标题"""
        from app.services.topic_generator import TopicValidator
        
        validator = TopicValidator()
        result = validator.validate_title("短标题")
        
        assert result["valid"] is True
        assert any("过短" in w for w in result["warnings"])
    
    def test_validate_genre(self):
        """测试验证题材"""
        from app.services.topic_generator import TopicValidator
        
        validator = TopicValidator()
        
        assert validator.validate_genre("都市言情") is True
        assert validator.validate_genre("悬疑反转") is True
        assert validator.validate_genre("无效题材") is False
    
    def test_validate_style(self):
        """测试验证风格"""
        from app.services.topic_generator import TopicValidator
        
        validator = TopicValidator()
        
        assert validator.validate_style("comic") is True
        assert validator.validate_style("realistic") is True
        assert validator.validate_style("invalid_style") is False


# ============ 集成测试 ============

class TestTopicGeneratorIntegration:
    """选题生成集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_topic_generation(self):
        """测试完整选题生成流程"""
        from app.services.topic_generator import TopicGenerator
        
        generator = TopicGenerator()
        
        # 生成选题
        topic = await generator.generate("test-project-id")
        
        # 验证
        assert topic is not None
        assert "title" in topic
        assert "genre" in topic
        assert "style" in topic
        
        # 验证标题长度
        title_length = len(topic["title"])
        assert 15 <= title_length <= 35, f"标题长度 {title_length} 不在推荐范围内"