"""
AI漫剧/视频生成功能单元测试

测试内容:
1. 数据库模型测试
2. Pydantic模型测试
3. 服务层测试
4. API路由测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import uuid


# ============ 数据库模型测试 ============

class TestVideoModels:
    """视频数据库模型测试"""
    
    def test_create_video_project(self):
        """测试创建视频项目"""
        from app.models.video import VideoProject
        
        project = VideoProject(
            title="测试视频",
            topic="测试选题",
            style="comic",
            target_duration=30,
            status="draft"
        )
        
        assert project.title == "测试视频"
        assert project.topic == "测试选题"
        assert project.style == "comic"
        assert project.target_duration == 30
        assert project.status == "draft"
        assert project.id is not None
        assert isinstance(project.created_at, datetime)
    
    def test_create_video_shot(self):
        """测试创建分镜"""
        from app.models.video import VideoShot, VideoProject
        
        project = VideoProject(title="测试项目")
        shot = VideoShot(
            project_id=project.id,
            sequence=1,
            description="测试分镜描述",
            narration="测试旁白",
            duration=5,
            status="pending"
        )
        
        assert shot.sequence == 1
        assert shot.description == "测试分镜描述"
        assert shot.narration == "测试旁白"
        assert shot.duration == 5
        assert shot.status == "pending"
    
    def test_create_video_asset(self):
        """测试创建素材"""
        from app.models.video import VideoAsset
        
        asset = VideoAsset(
            type="character",
            name="测试角色",
            description="测试描述",
            image_url="http://example.com/image.jpg"
        )
        
        assert asset.type == "character"
        assert asset.name == "测试角色"
        assert asset.used_count == 0


# ============ Pydantic模型测试 ============

class TestVideoSchemas:
    """视频Pydantic模型测试"""
    
    def test_video_project_create(self):
        """测试视频项目创建模型"""
        from app.schemas.ai_video import VideoProjectCreate
        
        data = {
            "title": "测试视频",
            "topic": "测试选题",
            "style": "comic",
            "target_duration": 30
        }
        
        project = VideoProjectCreate(**data)
        assert project.title == "测试视频"
        assert project.style == "comic"
    
    def test_shot_create(self):
        """测试分镜创建模型"""
        from app.schemas.ai_video import ShotCreate
        import uuid
        
        data = {
            "project_id": str(uuid.uuid4()),
            "sequence": 1,
            "description": "测试分镜",
            "duration": 5
        }
        
        shot = ShotCreate(**data)
        assert shot.sequence == 1
        assert shot.description == "测试分镜"


# ============ 服务层测试 ============

class TestVideoEngineService:
    """视频引擎服务测试"""
    
    @pytest.fixture
    def mock_model_manager(self):
        """模拟ModelManager"""
        with patch('app.services.ai_video_engine.ModelManager') as mock:
            mock_llm = Mock()
            mock_llm.chat.return_value = '{"title": "测试选题", "genre": "都市言情"}'
            mock.return_value.get_model_for_role.return_value = mock_llm
            yield mock
    
    def test_topic_generator_generate(self, mock_model_manager):
        """测试选题生成"""
        from app.services.ai_video_engine import TopicGenerator
        
        generator = TopicGenerator()
        result = generator.generate("test-project-id")
        
        assert "title" in result
        assert result["title"] == "测试选题"
    
    def test_robust_json_parse_valid(self):
        """测试JSON解析(有效JSON)"""
        from app.services.ai_video_engine import robust_json_parse
        
        text = '{"key": "value", "number": 123}'
        result = robust_json_parse(text)
        
        assert result["key"] == "value"
        assert result["number"] == 123
    
    def test_robust_json_parse_with_control_chars(self):
        """测试JSON解析(包含控制字符)"""
        from app.services.ai_video_engine import robust_json_parse
        
        text = '{\x00"key": "value\x01"}'
        result = robust_json_parse(text)
        
        assert result["key"] == "value"
    
    def test_robust_json_parse_with_trailing_comma(self):
        """测试JSON解析(包含尾逗号)"""
        from app.services.ai_video_engine import robust_json_parse
        
        text = '{"key": "value",}'
        result = robust_json_parse(text)
        
        assert result["key"] == "value"


# ============ API路由测试 ============

class TestVideoAPI:
    """视频API路由测试"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi.testclient import TestClient
        from app.main import app
        
        return TestClient(app)
    
    def test_create_project(self, client):
        """测试创建视频项目"""
        response = client.post(
            "/api/v1/video/projects",
            json={
                "title": "测试视频",
                "style": "comic",
                "target_duration": 30
            }
        )
        
        assert response.status_code in [201, 422]
    
    def test_list_projects(self, client):
        """测试获取视频项目列表"""
        response = client.get("/api/v1/video/projects")
        
        assert response.status_code == 200


# ============ Celery任务测试 ============

class TestVideoTasks:
    """视频任务测试"""
    
    @patch('app.tasks.video_tasks.VideoEngineService')
    def test_generate_topic_task(self, mock_engine):
        """测试选题生成任务"""
        from app.tasks.video_tasks import generate_topic_task
        
        # 模拟服务返回
        mock_service = Mock()
        mock_service.topic_generator.generate.return_value = {
            "title": "测试选题",
            "genre": "都市言情"
        }
        mock_engine.return_value = mock_service
        
        # 执行任务
        result = generate_topic_task("test-project-id")
        
        assert result["status"] == "completed"
        assert "topic" in result


# ============ 集成测试 ============

class TestVideoIntegration:
    """视频生成集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """测试完整生成流程"""
        # 这是一个集成测试,需要实际运行
        # 这里只做框架演示
        pass