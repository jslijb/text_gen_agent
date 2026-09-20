"""
素材生成模块

功能:
- 生成角色图像(多角度、表情变化)
- 生成场景图像(不同角度、不同时间)
- 素材库管理(可复用)
- 支持多种风格:漫画、写实、动漫
"""

import logging
import os
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.model_manager import ModelManager
from app.config.prompts.prompt_loader import load_prompt
from app.config.settings import settings

logger = logging.getLogger(__name__)


class AssetGenerator:
    """素材生成器"""
    
    def __init__(self):
        self.model_manager = ModelManager()
        self.image_model = self.model_manager.get_model_for_role("image_generator")
        self.prompt_template = load_prompt("video.yaml", "image_generation")
        self.assets_dir = os.path.join(settings.STATIC_DIR, "assets")
        os.makedirs(self.assets_dir, exist_ok=True)
    
    async def generate(self, project_id: str, shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        生成素材
        
        Args:
            project_id: 项目ID
            shots: 分镜列表
            
        Returns:
            素材列表
        """
        logger.info(f"开始生成素材: project_id={project_id}, shots={len(shots)}")
        
        assets = []
        
        for i, shot in enumerate(shots):
            # 生成角色图像
            character_asset = await self._generate_character(project_id, shot, i)
            if character_asset:
                assets.append(character_asset)
            
            # 生成场景图像
            scene_asset = await self._generate_scene(project_id, shot, i)
            if scene_asset:
                assets.append(scene_asset)
        
        logger.info(f"素材生成完成: assets={len(assets)}")
        
        return assets
    
    async def _generate_character(
        self, 
        project_id: str, 
        shot: Dict[str, Any], 
        index: int
    ) -> Optional[Dict[str, Any]]:
        """生成角色图像"""
        try:
            # 构建图像提示词
            prompt = self._build_character_prompt(shot)
            
            # 调用图像生成API
            image_url = await self._generate_image(prompt)
            
            # 创建素材记录
            asset = {
                "id": str(uuid.uuid4()),
                "type": "character",
                "name": f"角色_{index+1}",
                "description": shot.get("description", ""),
                "image_url": image_url,
                "metadata": {
                    "shot_id": index,
                    "prompt": prompt,
                    "created_at": datetime.utcnow().isoformat()
                }
            }
            
            return asset
            
        except Exception as e:
            logger.error(f"生成角色图像失败: {e}")
            return None
    
    async def _generate_scene(
        self, 
        project_id: str, 
        shot: Dict[str, Any], 
        index: int
    ) -> Optional[Dict[str, Any]]:
        """生成场景图像"""
        try:
            # 构建图像提示词
            prompt = self._build_scene_prompt(shot)
            
            # 调用图像生成API
            image_url = await self._generate_image(prompt)
            
            # 创建素材记录
            asset = {
                "id": str(uuid.uuid4()),
                "type": "scene",
                "name": f"场景_{index+1}",
                "description": shot.get("description", ""),
                "image_url": image_url,
                "metadata": {
                    "shot_id": index,
                    "prompt": prompt,
                    "created_at": datetime.utcnow().isoformat()
                }
            }
            
            return asset
            
        except Exception as e:
            logger.error(f"生成场景图像失败: {e}")
            return None
    
    async def _generate_image(self, prompt: str) -> str:
        """生成图像"""
        # 调用图像生成API
        # 这里使用ModelManager中配置的图像生成模型
        
        # TODO: 实际调用图像生成API
        # 暂时返回占位符URL
        return f"https://placeholder.com/image/{uuid.uuid4()}.png"
    
    def _build_character_prompt(self, shot: Dict[str, Any]) -> str:
        """构建角色图像提示词"""
        description = shot.get("description", "")
        image_prompt = shot.get("image_prompt", "")
        
        # 构建提示词
        prompt = f"{image_prompt},角色特写,漫画风格,高清,细节丰富,8k"
        
        return prompt
    
    def _build_scene_prompt(self, shot: Dict[str, Any]) -> str:
        """构建场景图像提示词"""
        description = shot.get("description", "")
        image_prompt = shot.get("image_prompt", "")
        
        # 构建提示词
        prompt = f"{image_prompt},场景,背景,漫画风格,高清,细节丰富,8k"
        
        return prompt
    
    async def generate_character_variants(
        self, 
        project_id: str, 
        shot: Dict[str, Any], 
        variants: List[str] = ["正面", "侧面", "微笑", "严肃"]
    ) -> List[Dict[str, Any]]:
        """生成角色变体(多角度、表情)"""
        assets = []
        
        for variant in variants:
            try:
                # 构建变体提示词
                prompt = f"{shot.get('image_prompt', '')},角色{variant},漫画风格,高清"
                
                # 生成图像
                image_url = await self._generate_image(prompt)
                
                # 创建素材记录
                asset = {
                    "id": str(uuid.uuid4()),
                    "type": "character",
                    "name": f"角色_{variant}",
                    "description": f"角色{variant}变体",
                    "image_url": image_url,
                    "metadata": {
                        "variant": variant,
                        "prompt": prompt,
                        "created_at": datetime.utcnow().isoformat()
                    }
                }
                
                assets.append(asset)
                
            except Exception as e:
                logger.error(f"生成角色变体失败({variant}): {e}")
        
        return assets


class AssetManager:
    """素材管理器"""
    
    def __init__(self):
        self.assets_dir = os.path.join(settings.STATIC_DIR, "assets")
        os.makedirs(self.assets_dir, exist_ok=True)
    
    def save_asset(self, asset: Dict[str, Any]) -> str:
        """保存素材"""
        asset_id = asset.get("id", str(uuid.uuid4()))
        filepath = os.path.join(self.assets_dir, f"{asset_id}.json")
        
        with open(filepath, "w", encoding="utf-8") as f:
            import json
            json.dump(asset, f, ensure_ascii=False, indent=2)
        
        return asset_id
    
    def load_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """加载素材"""
        filepath = os.path.join(self.assets_dir, f"{asset_id}.json")
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, "r", encoding="utf-8") as f:
            import json
            return json.load(f)
    
    def list_assets(self, asset_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出素材"""
        assets = []
        
        for filename in os.listdir(self.assets_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.assets_dir, filename)
                
                with open(filepath, "r", encoding="utf-8") as f:
                    import json
                    asset = json.load(f)
                    
                    if asset_type is None or asset.get("type") == asset_type:
                        assets.append(asset)
        
        return assets
    
    def delete_asset(self, asset_id: str) -> bool:
        """删除素材"""
        filepath = os.path.join(self.assets_dir, f"{asset_id}.json")
        
        if not os.path.exists(filepath):
            return False
        
        os.remove(filepath)
        return True


class AssetQualityChecker:
    """素材质量检查器"""
    
    @staticmethod
    def check_asset(asset: Dict[str, Any]) -> Dict[str, Any]:
        """检查素材质量"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "score": 100
        }
        
        # 检查类型
        if "type" not in asset:
            result["errors"].append("缺少类型")
            result["valid"] = False
            result["score"] -= 30
        
        # 检查图像URL
        if "image_url" not in asset or not asset["image_url"]:
            result["errors"].append("缺少图像URL")
            result["valid"] = False
            result["score"] -= 30
        
        # 检查名称
        if "name" not in asset or not asset["name"]:
            result["warnings"].append("缺少名称")
            result["score"] -= 10
        
        # 检查描述
        if "description" not in asset or not asset["description"]:
            result["warnings"].append("缺少描述")
            result["score"] -= 10
        
        return result
    
    @staticmethod
    def check_assets(assets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """检查素材列表质量"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "total_score": 0,
            "average_score": 0
        }
        
        if not assets:
            result["errors"].append("素材列表为空")
            result["valid"] = False
            return result
        
        # 检查每个素材
        total_score = 0
        for i, asset in enumerate(assets):
            asset_result = AssetQualityChecker.check_asset(asset)
            total_score += asset_result["score"]
            
            if not asset_result["valid"]:
                result["errors"].append(f"第{i+1}个素材: {asset_result['errors']}")
            
            result["warnings"].extend([f"第{i+1}个素材: {w}" for w in asset_result["warnings"]])
        
        result["total_score"] = total_score
        result["average_score"] = total_score / len(assets)
        
        if result["average_score"] < 60:
            result["valid"] = False
        
        return result