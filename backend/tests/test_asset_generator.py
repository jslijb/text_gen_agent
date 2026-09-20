"""
素材生成模块单元测试

测试内容:
1. 素材生成测试
2. 素材管理测试
3. 素材质量检查测试
"""

import pytest
import os
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestAssetGenerator:
    """素材生成器测试"""
    
    @pytest.fixture
    def mock_image_model(self):
        """模拟图像生成模型"""
        with patch('app.services.asset_generator.ModelManager') as mock:
            mock_model = Mock()
            mock_model.generate.return_value = "https://example.com/image.png"
            mock.return_value.get_model_for_role.return_value = mock_model
            yield mock
    
    @pytest.mark.asyncio
    async def test_generate_character(self, mock_image_model):
        """测试生成角色图像"""
        from app.services.asset_generator import AssetGenerator
        
        generator = AssetGenerator()
        shot = {
            "description": "女主角在教室里",
            "image_prompt": "漫画风格,教室,阳光"
        }
        
        asset = await generator._generate_character("test-project-id", shot, 0)
        
        assert asset is not None
        assert asset["type"] == "character"
        assert "name" in asset
        assert "image_url" in asset
    
    @pytest.mark.asyncio
    async def test_generate_scene(self, mock_image_model):
        """测试生成场景图像"""
        from app.services.asset_generator import AssetGenerator
        
        generator = AssetGenerator()
        shot = {
            "description": "教室场景",
            "image_prompt": "漫画风格,教室,阳光"
        }
        
        asset = await generator._generate_scene("test-project-id", shot, 0)
        
        assert asset is not None
        assert asset["type"] == "scene"
        assert "name" in asset
        assert "image_url" in asset
    
    @pytest.mark.asyncio
    async def test_generate_character_variants(self, mock_image_model):
        """测试生成角色变体"""
        from app.services.asset_generator import AssetGenerator
        
        generator = AssetGenerator()
        shot = {
            "description": "女主角",
            "image_prompt": "漫画风格,女主角"
        }
        
        variants = ["正面", "侧面", "微笑"]
        assets = await generator.generate_character_variants("test-project-id", shot, variants)
        
        assert len(assets) == 3
        assert all(asset["type"] == "character" for asset in assets)
    
    def test_build_character_prompt(self):
        """测试构建角色提示词"""
        from app.services.asset_generator import AssetGenerator
        
        generator = AssetGenerator()
        shot = {
            "description": "女主角",
            "image_prompt": "漫画风格,女主角"
        }
        
        prompt = generator._build_character_prompt(shot)
        
        assert "漫画风格" in prompt
        assert "角色特写" in prompt
    
    def test_build_scene_prompt(self):
        """测试构建场景提示词"""
        from app.services.asset_generator import AssetGenerator
        
        generator = AssetGenerator()
        shot = {
            "description": "教室",
            "image_prompt": "漫画风格,教室"
        }
        
        prompt = generator._build_scene_prompt(shot)
        
        assert "漫画风格" in prompt
        assert "场景" in prompt


class TestAssetManager:
    """素材管理器测试"""
    
    def test_save_and_load_asset(self, tmp_path):
        """测试保存和加载素材"""
        from app.services.asset_generator import AssetManager
        from app.config.settings import settings
        
        # 使用临时目录
        settings.STATIC_DIR = str(tmp_path)
        
        manager = AssetManager()
        
        # 保存素材
        asset = {
            "id": "test-asset-id",
            "type": "character",
            "name": "测试角色",
            "image_url": "https://example.com/image.png"
        }
        
        asset_id = manager.save_asset(asset)
        assert asset_id == "test-asset-id"
        
        # 加载素材
        loaded = manager.load_asset("test-asset-id")
        assert loaded is not None
        assert loaded["name"] == "测试角色"
    
    def test_list_assets(self, tmp_path):
        """测试列出素材"""
        from app.services.asset_generator import AssetManager
        from app.config.settings import settings
        
        # 使用临时目录
        settings.STATIC_DIR = str(tmp_path)
        
        manager = AssetManager()
        
        # 保存几个素材
        manager.save_asset({"id": "1", "type": "character", "name": "角色1"})
        manager.save_asset({"id": "2", "type": "scene", "name": "场景1"})
        manager.save_asset({"id": "3", "type": "character", "name": "角色2"})
        
        # 列出所有素材
        all_assets = manager.list_assets()
        assert len(all_assets) == 3
        
        # 按类型筛选
        character_assets = manager.list_assets("character")
        assert len(character_assets) == 2
    
    def test_delete_asset(self, tmp_path):
        """测试删除素材"""
        from app.services.asset_generator import AssetManager
        from app.config.settings import settings
        
        # 使用临时目录
        settings.STATIC_DIR = str(tmp_path)
        
        manager = AssetManager()
        
        # 保存素材
        manager.save_asset({"id": "test-id", "type": "character", "name": "测试角色"})
        
        # 删除素材
        result = manager.delete_asset("test-id")
        assert result is True
        
        # 确认已删除
        loaded = manager.load_asset("test-id")
        assert loaded is None


class TestAssetQualityChecker:
    """素材质量检查器测试"""
    
    def test_check_valid_asset(self):
        """测试检查有效素材"""
        from app.services.asset_generator import AssetQualityChecker
        
        asset = {
            "type": "character",
            "name": "测试角色",
            "description": "测试描述",
            "image_url": "https://example.com/image.png"
        }
        
        result = AssetQualityChecker.check_asset(asset)
        
        assert result["valid"] is True
        assert result["score"] == 100
    
    def test_check_invalid_asset(self):
        """测试检查无效素材"""
        from app.services.asset_generator import AssetQualityChecker
        
        asset = {}
        
        result = AssetQualityChecker.check_asset(asset)
        
        assert result["valid"] is False
        assert result["score"] < 100
    
    def test_check_asset_missing_url(self):
        """测试检查缺少URL的素材"""
        from app.services.asset_generator import AssetQualityChecker
        
        asset = {
            "type": "character",
            "name": "测试角色"
        }
        
        result = AssetQualityChecker.check_asset(asset)
        
        assert result["valid"] is False
        assert "缺少图像URL" in result["errors"]
    
    def test_check_assets(self):
        """测试检查素材列表"""
        from app.services.asset_generator import AssetQualityChecker
        
        assets = [
            {
                "type": "character",
                "name": "角色1",
                "image_url": "https://example.com/1.png"
            },
            {
                "type": "scene",
                "name": "场景1",
                "image_url": "https://example.com/2.png"
            }
        ]
        
        result = AssetQualityChecker.check_assets(assets)
        
        assert result["valid"] is True
        assert result["average_score"] >= 80
    
    def test_check_empty_assets(self):
        """测试检查空素材列表"""
        from app.services.asset_generator import AssetQualityChecker
        
        result = AssetQualityChecker.check_assets([])
        
        assert result["valid"] is False
        assert "素材列表为空" in result["errors"]


# ============ 集成测试 ============

class TestAssetGeneratorIntegration:
    """素材生成集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_asset_generation(self):
        """测试完整素材生成流程"""
        from app.services.asset_generator import AssetGenerator
        
        generator = AssetGenerator()
        
        # 生成素材
        shots = [
            {
                "description": "女主角在教室里",
                "image_prompt": "漫画风格,教室,阳光",
                "narration": "重生回19岁",
                "duration": 5
            },
            {
                "description": "女主角特写",
                "image_prompt": "漫画风格,女主角,特写",
                "narration": "她做了一个决定",
                "duration": 5
            }
        ]
        
        assets = await generator.generate("test-project-id", shots)
        
        # 验证
        assert assets is not None
        assert len(assets) > 0
        
        # 验证每个素材
        for asset in assets:
            assert "type" in asset
            assert "image_url" in asset