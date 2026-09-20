"""
视频生成模块单元测试

测试内容:
1. 模型选择测试
2. 黑名单机制测试
3. 403处理测试
4. 视频质量检查测试
"""

import pytest
import httpx
from unittest.mock import Mock, patch, MagicMock


class TestVideoGenerator:
    """视频生成器测试"""
    
    @pytest.fixture
    def mock_httpx(self):
        """模拟httpx"""
        with patch('app.services.video_generator.httpx') as mock:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"url": "https://example.com/video.mp4"}
            mock.post.return_value = mock_response
            mock.get.return_value = mock_response
            yield mock
    
    @pytest.mark.asyncio
    async def test_generate_with_agnes(self, mock_httpx):
        """测试使用Agnes生成视频"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        shot = {
            "video_prompt": "测试视频提示词"
        }
        
        # 模拟环境变量
        with patch.dict('os.environ', {'AGNES_KEY': 'test-key'}):
            video_url = await generator._generate_with_agnes(
                "test-project-id", shot, None, 0
            )
            
            assert video_url is not None
    
    @pytest.mark.asyncio
    async def test_generate_with_dashscope(self, mock_httpx):
        """测试使用DashScope生成视频"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        shot = {
            "video_prompt": "测试视频提示词"
        }
        
        # 模拟环境变量
        with patch.dict('os.environ', {'DASHSCOPE_API_KEY1': 'test-key'}):
            video_url = await generator._generate_with_dashscope(
                "test-project-id", shot, None, 0, "wan2.7-t2v-2026-06-12"
            )
            
            assert video_url is not None
    
    @pytest.mark.asyncio
    async def test_blacklist_mechanism(self, mock_httpx):
        """测试黑名单机制"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        
        # 添加黑名单
        generator.blacklist.add("test-model")
        
        assert "test-model" in generator.blacklist
        
        # 清空黑名单
        generator.clear_blacklist()
        
        assert "test-model" not in generator.blacklist
    
    def test_get_current_model(self):
        """测试获取当前模型"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        generator.current_model = "test-model"
        
        assert generator.get_current_model() == "test-model"
    
    def test_find_asset_for_shot(self):
        """测试查找分镜对应的素材"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        
        assets = [
            {"id": "1", "metadata": {"shot_id": 0}},
            {"id": "2", "metadata": {"shot_id": 1}},
            {"id": "3", "metadata": {"shot_id": 2}}
        ]
        
        # 精确匹配
        asset = generator._find_asset_for_shot(assets, 1)
        assert asset["id"] == "2"
        
        # 无匹配,返回第一个
        asset = generator._find_asset_for_shot(assets, 99)
        assert asset["id"] == "1"


class TestVideoQualityChecker:
    """视频质量检查器测试"""
    
    def test_check_valid_video(self):
        """测试检查有效视频"""
        from app.services.video_generator import VideoQualityChecker
        
        result = VideoQualityChecker.check_video("https://example.com/video.mp4")
        
        assert result["valid"] is True
        assert result["score"] == 100
    
    def test_check_invalid_video(self):
        """测试检查无效视频"""
        from app.services.video_generator import VideoQualityChecker
        
        result = VideoQualityChecker.check_video("")
        
        assert result["valid"] is False
        assert result["score"] < 100
    
    def test_check_invalid_url(self):
        """测试检查无效URL"""
        from app.services.video_generator import VideoQualityChecker
        
        result = VideoQualityChecker.check_video("invalid-url")
        
        assert result["valid"] is False
        assert "无效的视频URL" in result["errors"]
    
    def test_check_videos(self):
        """测试检查视频列表"""
        from app.services.video_generator import VideoQualityChecker
        
        videos = [
            "https://example.com/video1.mp4",
            "https://example.com/video2.mp4"
        ]
        
        result = VideoQualityChecker.check_videos(videos)
        
        assert result["valid"] is True
        assert result["average_score"] == 100
    
    def test_check_empty_videos(self):
        """测试检查空视频列表"""
        from app.services.video_generator import VideoQualityChecker
        
        result = VideoQualityChecker.check_videos([])
        
        assert result["valid"] is False
        assert "视频列表为空" in result["errors"]


# ============ 集成测试 ============

class TestVideoGeneratorIntegration:
    """视频生成集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_video_generation(self):
        """测试完整视频生成流程"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        
        # 生成视频
        shots = [
            {
                "description": "女主角在教室里",
                "video_prompt": "漫画风格,女主角在教室里,阳光从窗户照入",
                "duration": 5
            },
            {
                "description": "女主角特写",
                "video_prompt": "漫画风格,女主角特写,坚定的眼神",
                "duration": 5
            }
        ]
        
        assets = [
            {
                "id": "asset-1",
                "image_url": "https://example.com/image1.png",
                "metadata": {"shot_id": 0}
            },
            {
                "id": "asset-2",
                "image_url": "https://example.com/image2.png",
                "metadata": {"shot_id": 1}
            }
        ]
        
        # 注意:这个测试需要实际调用API,可能会失败
        # 这里只做框架演示
        pass


# ============ 403处理测试 ============

class Test403Handling:
    """403处理测试"""
    
    @pytest.mark.asyncio
    async def test_403_with_agnes(self):
        """测试Agnes 403处理"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        
        # 模拟403响应
        with patch('app.services.video_generator.httpx.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.text = "Forbidden"
            mock_post.return_value = mock_response
            
            with patch.dict('os.environ', {'AGNES_KEY': 'test-key'}):
                with pytest.raises(Exception, match="403"):
                    await generator._generate_with_agnes(
                        "test-project-id", {}, None, 0
                    )
    
    @pytest.mark.asyncio
    async def test_403_with_dashscope(self):
        """测试DashScope 403处理"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        
        # 模拟403响应
        with patch('app.services.video_generator.httpx.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.text = "Forbidden"
            mock_post.return_value = mock_response
            
            with patch.dict('os.environ', {'DASHSCOPE_API_KEY1': 'test-key'}):
                with pytest.raises(Exception, match="403"):
                    await generator._generate_with_dashscope(
                        "test-project-id", {}, None, 0, "wan2.7-t2v-2026-06-12"
                    )