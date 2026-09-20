"""
批量生产模块单元测试

测试内容:
1. 批量创建项目测试
2. 批量生成视频测试
3. 进度追踪测试
4. 批量验证测试
"""

import pytest
import asyncio
from unittest.mock import Mock, patch


class TestBatchProducer:
    """批量生产者测试"""
    
    @pytest.mark.asyncio
    async def test_create_batch_projects(self):
        """测试批量创建项目"""
        from app.services.batch_producer import BatchProducer
        
        producer = BatchProducer(max_concurrent=5)
        
        # 创建5个项目
        projects = await producer.create_batch_projects(
            count=5,
            genres=["都市言情", "悬疑反转"]
        )
        
        assert len(projects) == 5
        assert all("id" in p for p in projects)
        assert all("title" in p for p in projects)
    
    @pytest.mark.asyncio
    async def test_create_batch_projects_with_genres(self):
        """测试批量创建项目(指定题材)"""
        from app.services.batch_producer import BatchProducer
        
        producer = BatchProducer()
        
        # 创建3个项目,只选择题材
        projects = await producer.create_batch_projects(
            count=3,
            genres=["都市言情"]
        )
        
        assert len(projects) == 3
    
    @pytest.mark.asyncio
    async def test_generate_batch_videos(self):
        """测试批量生成视频"""
        from app.services.batch_producer import BatchProducer
        
        producer = BatchProducer(max_concurrent=2)
        
        # 创建测试项目
        projects = [
            {"id": f"test-project-{i}"} for i in range(3)
        ]
        
        # 模拟视频生成
        with patch.object(producer.engine, 'full_pipeline') as mock_pipeline:
            mock_pipeline.return_value = {
                "video_url": "https://example.com/video.mp4"
            }
            
            result = await producer.generate_batch_videos(projects)
            
            assert result is not None
            assert "total" in result
            assert "completed" in result
            assert "failed" in result
    
    def test_get_batch_status(self):
        """测试获取批量状态"""
        from app.services.batch_producer import BatchProducer
        
        producer = BatchProducer()
        
        # 获取不存在的任务
        status = producer.get_batch_status("non-existent")
        
        assert status is None
    
    def test_cancel_batch(self):
        """测试取消批量任务"""
        from app.services.batch_producer import BatchProducer
        
        producer = BatchProducer()
        
        # 取消不存在的任务
        result = producer.cancel_batch("non-existent")
        
        assert result is False


class TestProgressTracker:
    """进度追踪器测试"""
    
    def test_start(self):
        """测试开始任务"""
        from app.services.batch_producer import ProgressTracker
        
        tracker = ProgressTracker()
        
        task_id = "test-task"
        tracker.start(task_id, 10)
        
        progress = tracker.get_progress(task_id)
        
        assert progress is not None
        assert progress["total"] == 10
        assert progress["status"] == "running"
    
    def test_update(self):
        """测试更新进度"""
        from app.services.batch_producer import ProgressTracker
        
        tracker = ProgressTracker()
        
        task_id = "test-task"
        tracker.start(task_id, 10)
        tracker.update(task_id, 5)
        
        progress = tracker.get_progress(task_id)
        
        assert progress["completed"] == 5
        assert progress["progress"] == 0.5
    
    def test_complete(self):
        """测试完成任务"""
        from app.services.batch_producer import ProgressTracker
        
        tracker = ProgressTracker()
        
        task_id = "test-task"
        tracker.start(task_id, 10)
        tracker.complete(task_id)
        
        progress = tracker.get_progress(task_id)
        
        assert progress["status"] == "completed"
    
    def test_get_progress(self):
        """测试获取进度"""
        from app.services.batch_producer import ProgressTracker
        
        tracker = ProgressTracker()
        
        # 获取不存在的任务
        progress = tracker.get_progress("non-existent")
        
        assert progress is None


class TestBatchScheduler:
    """批量调度器测试"""
    
    @pytest.mark.asyncio
    async def test_schedule_batch(self):
        """测试调度批量任务"""
        from app.services.batch_producer import BatchScheduler
        
        scheduler = BatchScheduler()
        
        # 调度批量任务
        with patch.object(scheduler.producer, 'create_batch_projects') as mock_create, \
             patch.object(scheduler.producer, 'generate_batch_videos') as mock_generate:
            
            mock_create.return_value = [{"id": f"test-{i}"} for i in range(3)]
            mock_generate.return_value = {
                "total": 3,
                "completed": 3,
                "failed": 0
            }
            
            result = await scheduler.schedule_batch(
                count=3,
                genres=["都市言情"]
            )
            
            assert result is not None
            assert "task_id" in result
            assert "projects" in result


class TestBatchValidator:
    """批量验证器测试"""
    
    def test_validate_valid_batch_size(self):
        """测试验证有效批量大小"""
        from app.services.batch_producer import BatchValidator
        
        validator = BatchValidator()
        
        result = validator.validate_batch_size(10)
        
        assert result["valid"] is True
        assert len(result["warnings"]) == 0
    
    def test_validate_invalid_batch_size(self):
        """测试验证无效批量大小"""
        from app.services.batch_producer import BatchValidator
        
        validator = BatchValidator()
        
        result = validator.validate_batch_size(0)
        
        assert result["valid"] is False
        assert len(result["warnings"]) > 0
    
    def test_validate_large_batch_size(self):
        """测试验证大批量大小"""
        from app.services.batch_producer import BatchValidator
        
        validator = BatchValidator()
        
        result = validator.validate_batch_size(150)
        
        assert result["valid"] is True
        assert any("过大" in w for w in result["warnings"])
    
    def test_validate_valid_genres(self):
        """测试验证有效题材"""
        from app.services.batch_producer import BatchValidator
        
        validator = BatchValidator()
        
        result = validator.validate_genres(["都市言情", "悬疑反转"])
        
        assert result["valid"] is True
        assert len(result["warnings"]) == 0
    
    def test_validate_invalid_genres(self):
        """测试验证无效题材"""
        from app.services.batch_producer import BatchValidator
        
        validator = BatchValidator()
        
        result = validator.validate_genres(["都市言情", "未知题材"])
        
        assert result["valid"] is True
        assert any("未知" in w for w in result["warnings"])


# ============ 集成测试 ============

class TestBatchProducerIntegration:
    """批量生产集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_batch_process(self):
        """测试完整批量流程"""
        from app.services.batch_producer import BatchScheduler
        
        scheduler = BatchScheduler()
        
        # 调度批量任务(使用Mock)
        with patch.object(scheduler.producer, 'create_batch_projects') as mock_create, \
             patch.object(scheduler.producer, 'generate_batch_videos') as mock_generate:
            
            mock_create.return_value = [{"id": f"test-{i}"} for i in range(5)]
            mock_generate.return_value = {
                "batch_id": "test-batch",
                "total": 5,
                "completed": 5,
                "failed": 0,
                "success_rate": "100%"
            }
            
            result = await scheduler.schedule_batch(
                count=5,
                genres=["都市言情", "悬疑反转"]
            )
            
            assert result is not None
            assert "task_id" in result
            assert result["projects"] == 5


# ============ 性能测试 ============

class TestBatchProducerPerformance:
    """批量生产性能测试"""
    
    @pytest.mark.performance
    def test_create_batch_projects_performance(self):
        """测试批量创建项目性能"""
        import time
        from app.services.batch_producer import BatchProducer
        
        producer = BatchProducer()
        
        start_time = time.time()
        
        # 创建10个项目
        with patch.object(producer.strategy, 'get_competitor_analysis') as mock_strategy:
            mock_strategy.return_value = {"漫剧工厂": {}}
            
            # 运行异步函数
            asyncio.run(producer.create_batch_projects(10))
        
        elapsed = time.time() - start_time
        
        # 验证性能(10个项目应该在2秒内完成)
        assert elapsed < 2.0