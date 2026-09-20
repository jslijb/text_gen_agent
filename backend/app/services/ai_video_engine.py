"""
AI漫剧/视频生成引擎服务

协调各子服务完成完整的视频生成流程:
选题生成 → 文案创作 → 分镜拆分 → 素材生成 → 视频合成 → 配音配乐 → 最终成片
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.model_manager import ModelManager
from app.services.topic_generator import TopicGenerator
from app.services.script_writer import ScriptWriter
from app.services.shot_splitter import ShotSplitter
from app.services.asset_generator import AssetGenerator
from app.services.video_generator import VideoGenerator
from app.services.audio_service import AudioService

logger = logging.getLogger(__name__)


class VideoEngineService:
    """视频生成主引擎"""
    
    def __init__(self):
        self.model_manager = ModelManager()
        self.topic_generator = TopicGenerator()
        self.script_writer = ScriptWriter()
        self.shot_splitter = ShotSplitter()
        self.asset_generator = AssetGenerator()
        self.video_generator = VideoGenerator()
        self.audio_service = AudioService()
    
    async def full_pipeline(self, project_id: str) -> Dict[str, Any]:
        """完整生成流程"""
        logger.info(f"开始完整生成流程: project_id={project_id}")
        
        try:
            # Step 1: 选题
            logger.info("Step 1: 生成选题")
            topic = await self.topic_generator.generate(project_id)
            
            # Step 2: 文案
            logger.info("Step 2: 生成文案")
            script = await self.script_writer.generate(project_id, topic)
            
            # Step 3: 分镜
            logger.info("Step 3: 拆分分镜")
            shots = await self.shot_splitter.split(project_id, script)
            
            # Step 4: 素材
            logger.info("Step 4: 生成素材")
            assets = await self.asset_generator.generate(project_id, shots)
            
            # Step 5: 视频
            logger.info("Step 5: 生成视频")
            video_url = await self.video_generator.generate(project_id, shots, assets)
            
            # Step 6: 音频
            logger.info("Step 6: 生成音频")
            audio_url = await self.audio_service.generate(project_id, script)
            
            # Step 7: 合成最终视频
            logger.info("Step 7: 合成最终视频")
            final_video = await self._compose(video_url, audio_url)
            
            logger.info(f"生成流程完成: project_id={project_id}")
            
            return {
                "project_id": project_id,
                "video_url": final_video,
                "shots": len(shots),
                "assets": len(assets),
                "topic": topic,
                "script": script
            }
        except Exception as e:
            logger.error(f"生成流程失败: {e}", exc_info=True)
            raise



class ScriptWriter:
    """自动文案生成模块"""
    
    def __init__(self):
        self.llm = ModelManager().get_model_for_role("script_writer")
    
    async def generate(self, project_id: str, topic: Dict[str, Any]) -> Dict[str, Any]:
        """生成文案"""
        prompt = self._build_prompt(topic)
        
        response = await self.llm.chat(prompt)
        script = self._parse_response(response)
        
        return script
    
    def _build_prompt(self, topic: Dict[str, Any]) -> str:
        """构建文案Prompt"""
        return f"""你是一个AI漫剧文案专家。根据以下选题生成适合短视频的漫剧文案。

选题: {topic.get('title', '')}
题材: {topic.get('genre', '')}
风格: {topic.get('style', '')}
目标时长: {topic.get('target_duration', 30)}秒

文案要求:
1. 标题17-30字,符合快手平台规范
2. 适合AI漫剧叙事节奏,每5-10秒一个镜头切换
3. 开头3秒必须有钩子(悬念、冲突、反转)
4. 包含旁白、对话、音效提示
5. 结尾留悬念引导追更

返回JSON格式:
{{
  "title": "文案标题",
  "content": "完整的文案内容",
  "shots": [
    {{
      "sequence": 1,
      "duration": 5,
      "description": "画面描述",
      "narration": "旁白文本",
      "sound_effects": "音效提示"
    }}
  ]
}}"""
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析文案响应"""
        from app.services.utils.json_parser import robust_json_parse
        return robust_json_parse(response)


class ShotSplitter:
    """自动分镜模块 - 使用独立模块"""
    
    def __init__(self):
        from app.services.shot_splitter import ShotSplitter as Impl
        self.impl = Impl()
    
    async def split(self, project_id: str, script: Dict[str, Any]) -> List[Dict[str, Any]]:
        """拆分分镜"""
        return await self.impl.split(project_id, script)


class AssetGenerator:
    """素材生成模块 - 使用独立模块"""
    
    def __init__(self):
        from app.services.asset_generator import AssetGenerator as Impl
        self.impl = Impl()
    
    async def generate(self, project_id: str, shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成素材"""
        return await self.impl.generate(project_id, shots)


class VideoGenerator:
    """视频生成模块 - 使用独立模块"""
    
    def __init__(self):
        from app.services.video_generator import VideoGenerator as Impl
        self.impl = Impl()
    
    async def generate(self, project_id: str, shots: List[Dict[str, Any]], assets: List[Dict[str, Any]]) -> str:
        """生成视频"""
        return await self.impl.generate(project_id, shots, assets)
