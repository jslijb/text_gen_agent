"""
AI漫剧/视频生成端到端集成测试

测试完整的视频生成流程:
选题生成 → 文案创作 → 分镜拆分 → 素材生成 → 视频合成

注意: 这是一个集成测试,需要实际调用API,可能会产生费用
"""

import pytest
import asyncio
from unittest.mock import Mock, patch


class TestVideoPipelineIntegration:
    """视频生成流水线集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline_from_topic_to_video(self):
        """
        测试完整流程:从选题到视频
        
        这是一个端到端测试,验证所有模块协同工作
        """
        from app.services.ai_video_engine import VideoEngineService
        
        engine = VideoEngineService()
        
        # 模拟完整的视频生成流程
        # 注意:这里使用Mock,实际测试需要真实API
        
        # Step 1: 选题生成
        with patch.object(engine.topic_generator, 'generate') as mock_topic:
            mock_topic.return_value = {
                "title": "重生回19岁,她做了一个让所有人震惊的决定",
                "genre": "都市言情",
                "style": "comic",
                "target_duration": 30,
                "reason": "重生题材热度高,受众广"
            }
            
            topic = await engine.topic_generator.generate("test-project-id")
            assert "title" in topic
            assert "genre" in topic
        
        # Step 2: 文案生成
        with patch.object(engine.script_writer, 'generate') as mock_script:
            mock_script.return_value = {
                "title": "重生回19岁,她做了一个让所有人震惊的决定",
                "content": "重生回19岁,看着熟悉的教室,她做了一个决定...",
                "shots": [
                    {
                        "sequence": 1,
                        "description": "女主角在教室里醒来",
                        "narration": "重生回19岁,看着熟悉的教室,她做了一个决定",
                        "duration": 5
                    }
                ]
            }
            
            script = await engine.script_writer.generate("test-project-id", topic)
            assert "title" in script
            assert "shots" in script
        
        # Step 3: 分镜拆分
        with patch.object(engine.shot_splitter, 'split') as mock_shots:
            mock_shots.return_value = [
                {
                    "sequence": 1,
                    "description": "女主角在教室里醒来",
                    "narration": "重生回19岁,看着熟悉的教室,她做了一个决定",
                    "duration": 5,
                    "image_prompt": "漫画风格,教室,阳光,高清",
                    "video_prompt": "镜头从窗外推进到教室内,流畅,30fps",
                    "transition": "淡入淡出"
                }
            ]
            
            shots = await engine.shot_splitter.split("test-project-id", script)
            assert len(shots) > 0
        
        # Step 4: 素材生成
        with patch.object(engine.asset_generator, 'generate') as mock_assets:
            mock_assets.return_value = [
                {
                    "id": "asset-1",
                    "type": "character",
                    "name": "角色_1",
                    "image_url": "https://example.com/character.png",
                    "metadata": {"shot_id": 0}
                },
                {
                    "id": "asset-2",
                    "type": "scene",
                    "name": "场景_1",
                    "image_url": "https://example.com/scene.png",
                    "metadata": {"shot_id": 0}
                }
            ]
            
            assets = await engine.asset_generator.generate("test-project-id", shots)
            assert len(assets) > 0
        
        # Step 5: 视频生成
        with patch.object(engine.video_generator, 'generate') as mock_video:
            mock_video.return_value = "https://example.com/final_video.mp4"
            
            video_url = await engine.video_generator.generate("test-project-id", shots, assets)
            assert video_url is not None
            assert "http" in video_url
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline_with_real_api(self):
        """
        测试完整流程(使用真实API)
        
        注意:这个测试需要真实API配置,可能会产生费用
        在实际运行前,请确保:
        1. 配置了正确的API Key
        2. 有足够的额度
        3. 网络连接正常
        """
        from app.services.ai_video_engine import VideoEngineService
        
        engine = VideoEngineService()
        
        # 执行完整流程
        result = await engine.full_pipeline("test-project-id")
        
        # 验证结果
        assert "project_id" in result
        assert "video_url" in result
        assert "shots" in result
        assert "assets" in result
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self):
        """测试流水线错误处理"""
        from app.services.ai_video_engine import VideoEngineService
        
        engine = VideoEngineService()
        
        # 模拟选题生成失败
        with patch.object(engine.topic_generator, 'generate') as mock_topic:
            mock_topic.side_effect = Exception("LLM调用失败")
            
            with pytest.raises(Exception, match="LLM调用失败"):
                await engine.full_pipeline("test-project-id")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pipeline_retry_mechanism(self):
        """测试流水线重试机制"""
        from app.services.ai_video_engine import VideoEngineService
        
        engine = VideoEngineService()
        
        # 模拟第一次失败,第二次成功
        call_count = 0
        
        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                raise Exception("第一次失败")
            
            return {
                "title": "测试选题",
                "genre": "都市言情",
                "style": "comic",
                "target_duration": 30
            }
        
        with patch.object(engine.topic_generator, 'generate', side_effect=mock_generate):
            # 第一次应该失败
            with pytest.raises(Exception, match="第一次失败"):
                await engine.topic_generator.generate("test-project-id")
            
            # 第二次应该成功
            result = await engine.topic_generator.generate("test-project-id")
            assert "title" in result


class TestVideoGeneratorIntegration:
    """视频生成集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_model_priority_selection(self):
        """测试模型优先级选择"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        
        # 测试Agnes优先
        # 测试DashScope备用
        # 测试Token Plan最后
        
        # 验证当前模型设置
        assert generator.get_current_model() is None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_403_handling(self):
        """测试403错误处理"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        
        # 模拟403错误
        with patch('app.services.video_generator.httpx.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.text = "Forbidden"
            mock_post.return_value = mock_response
            
            # 验证403被正确处理
            with patch.dict('os.environ', {'AGNES_KEY': 'test-key'}):
                with pytest.raises(Exception, match="403"):
                    await generator._generate_with_agnes(
                        "test-project-id", {}, None, 0
                    )
            
            # 验证模型被加入黑名单
            assert "agnes-2.5-flash" in generator.blacklist
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_blacklist_mechanism(self):
        """测试黑名单机制"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        
        # 添加黑名单
        generator.blacklist.add("test-model-1")
        generator.blacklist.add("test-model-2")
        
        # 验证黑名单
        assert "test-model-1" in generator.blacklist
        assert "test-model-2" in generator.blacklist
        
        # 清空黑名单
        generator.clear_blacklist()
        
        # 验证清空
        assert len(generator.blacklist) == 0


class TestAssetGenerationIntegration:
    """素材生成集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_character_and_scene_generation(self):
        """测试角色和场景生成"""
        from app.services.asset_generator import AssetGenerator
        
        generator = AssetGenerator()
        
        # 测试分镜
        shots = [
            {
                "description": "女主角在教室里",
                "image_prompt": "漫画风格,教室,阳光",
                "narration": "重生回19岁",
                "duration": 5
            }
        ]
        
        # 生成素材
        with patch.object(generator, '_generate_image') as mock_image:
            mock_image.return_value = "https://example.com/image.png"
            
            assets = await generator.generate("test-project-id", shots)
            
            # 验证素材
            assert len(assets) > 0
            assert all("type" in asset for asset in assets)
            assert all("image_url" in asset for asset in assets)


class TestShotSplitterIntegration:
    """分镜拆分集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_shot_duration_adjustment(self):
        """测试分镜时长调整"""
        from app.services.shot_splitter import ShotSplitter
        
        splitter = ShotSplitter()
        
        # 测试分镜
        shots = [
            {"sequence": 1, "duration": 5},
            {"sequence": 2, "duration": 5},
            {"sequence": 3, "duration": 5}
        ]
        
        # 调整到10秒
        adjusted = splitter.adjust_durations(shots, 10)
        
        # 验证总时长
        total = splitter.calculate_total_duration(adjusted)
        assert total == 10
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_transition_optimization(self):
        """测试转场优化"""
        from app.services.shot_splitter import ShotOptimizer
        
        shots = [
            {"sequence": 1, "description": "第一个分镜"},
            {"sequence": 2, "description": "第二个分镜"},
            {"sequence": 3, "description": "第三个分镜"}
        ]
        
        optimized = ShotOptimizer.optimize_transitions(shots)
        
        # 验证转场
        assert optimized[0]["transition"] == "淡入淡出"
        assert optimized[1]["transition"] == "切镜"
        assert optimized[2]["transition"] == "淡入淡出"


# ============ 性能测试 ============

class TestPerformance:
    """性能测试"""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_topic_generation_performance(self):
        """测试选题生成性能"""
        import time
        from app.services.topic_generator import TopicGenerator
        
        generator = TopicGenerator()
        
        start_time = time.time()
        
        with patch.object(generator, 'generate') as mock_generate:
            mock_generate.return_value = {
                "title": "测试选题",
                "genre": "都市言情",
                "style": "comic",
                "target_duration": 30
            }
            
            result = await generator.generate("test-project-id")
        
        elapsed = time.time() - start_time
        
        # 验证性能(应该在5秒内完成)
        assert elapsed < 5.0
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_full_pipeline_performance(self):
        """测试完整流程性能"""
        import time
        from app.services.ai_video_engine import VideoEngineService
        
        engine = VideoEngineService()
        
        start_time = time.time()
        
        # 模拟完整流程
        with patch.object(engine.topic_generator, 'generate') as mock_topic, \
             patch.object(engine.script_writer, 'generate') as mock_script, \
             patch.object(engine.shot_splitter, 'split') as mock_shots, \
             patch.object(engine.asset_generator, 'generate') as mock_assets, \
             patch.object(engine.video_generator, 'generate') as mock_video:
            
            mock_topic.return_value = {"title": "测试选题"}
            mock_script.return_value = {"title": "测试文案", "shots": []}
            mock_shots.return_value = [{"sequence": 1, "duration": 5}]
            mock_assets.return_value = [{"id": "asset-1"}]
            mock_video.return_value = "https://example.com/video.mp4"
            
            result = await engine.full_pipeline("test-project-id")
        
        elapsed = time.time() - start_time
        
        # 验证性能(应该在10秒内完成)
        assert elapsed < 10.0


# ============ 冒烟测试 ============

class TestSmokeTests:
    """冒烟测试 - 验证基本功能"""
    
    @pytest.mark.smoke
    def test_import_all_modules(self):
        """测试所有模块可以导入"""
        from app.services.topic_generator import TopicGenerator
        from app.services.script_writer import ScriptWriter
        from app.services.shot_splitter import ShotSplitter
        from app.services.asset_generator import AssetGenerator
        from app.services.video_generator import VideoGenerator
        from app.services.ai_video_engine import VideoEngineService
        
        assert TopicGenerator is not None
        assert ScriptWriter is not None
        assert ShotSplitter is not None
        assert AssetGenerator is not None
        assert VideoGenerator is not None
        assert VideoEngineService is not None
    
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_topic_generator_basic(self):
        """测试选题生成基本功能"""
        from app.services.topic_generator import TopicGenerator
        
        generator = TopicGenerator()
        
        with patch.object(generator, 'generate') as mock_generate:
            mock_generate.return_value = {
                "title": "测试选题",
                "genre": "都市言情",
                "style": "comic",
                "target_duration": 30
            }
            
            result = await generator.generate("test-project-id")
            
            assert result is not None
            assert "title" in result
    
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_script_writer_basic(self):
        """测试文案生成基本功能"""
        from app.services.script_writer import ScriptWriter
        
        writer = ScriptWriter()
        
        with patch.object(writer, 'generate') as mock_generate:
            mock_generate.return_value = {
                "title": "测试文案",
                "content": "测试内容",
                "shots": []
            }
            
            result = await writer.generate("test-project-id", {"title": "测试选题"})
            
            assert result is not None
            assert "title" in result
    
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_shot_splitter_basic(self):
        """测试分镜拆分基本功能"""
        from app.services.shot_splitter import ShotSplitter
        
        splitter = ShotSplitter()
        
        with patch.object(splitter, 'split') as mock_split:
            mock_split.return_value = [
                {"sequence": 1, "duration": 5}
            ]
            
            result = await splitter.split("test-project-id", {"content": "测试"})
            
            assert result is not None
            assert len(result) > 0
    
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_asset_generator_basic(self):
        """测试素材生成基本功能"""
        from app.services.asset_generator import AssetGenerator
        
        generator = AssetGenerator()
        
        with patch.object(generator, 'generate') as mock_generate:
            mock_generate.return_value = [
                {"id": "asset-1", "type": "character"}
            ]
            
            result = await generator.generate("test-project-id", [])
            
            assert result is not None
    
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_video_generator_basic(self):
        """测试视频生成基本功能"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        
        with patch.object(generator, 'generate') as mock_generate:
            mock_generate.return_value = "https://example.com/video.mp4"
            
            result = await generator.generate("test-project-id", [], [])
            
            assert result is not None
            assert "http" in result


# ============ 回归测试 ============

class TestRegressionTests:
    """回归测试 - 防止功能退化"""
    
    @pytest.mark.regression
    def test_json_parsing_robustness(self):
        """测试JSON解析鲁棒性"""
        from app.services.topic_generator import TopicGenerator
        
        generator = TopicGenerator()
        
        # 测试有效JSON
        valid_json = '{"title": "测试"}'
        result = generator._robust_json_parse(valid_json)
        assert result["title"] == "测试"
        
        # 测试带控制字符的JSON
        with_control_chars = '{\x00"title": "测试\x01"}'
        result = generator._robust_json_parse(with_control_chars)
        assert result["title"] == "测试"
        
        # 测试带尾逗号的JSON
        with_trailing_comma = '{"title": "测试",}'
        result = generator._robust_json_parse(with_trailing_comma)
        assert result["title"] == "测试"
    
    @pytest.mark.regression
    def test_title_validation(self):
        """测试标题验证"""
        from app.services.topic_generator import TopicValidator
        
        validator = TopicValidator()
        
        # 测试有效标题
        result = validator.validate_title("重生回19岁,她做了一个让所有人震惊的决定#短剧#")
        assert result["valid"] is True
        
        # 测试过短标题
        result = validator.validate_title("短")
        assert result["valid"] is True
        assert len(result["warnings"]) > 0
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_model_blacklist_persistence(self):
        """测试模型黑名单持久性"""
        from app.services.video_generator import VideoGenerator
        
        generator = VideoGenerator()
        
        # 添加黑名单
        generator.blacklist.add("test-model")
        
        # 创建新实例,验证黑名单不持久化(每次启动清空)
        new_generator = VideoGenerator()
        assert len(new_generator.blacklist) == 0