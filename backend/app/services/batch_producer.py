"""
批量生产模块

功能:
- 批量创建视频项目
- 批量生成视频
- 并发控制
- 进度追踪
"""

import logging
import asyncio
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from app.services.ai_video_engine import VideoEngineService
from app.services.competitor_strategy import CompetitorStrategy

logger = logging.getLogger(__name__)


class BatchProducer:
    """批量生产者"""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.engine = VideoEngineService()
        self.strategy = CompetitorStrategy()
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        
        # 任务状态
        self.tasks: Dict[str, Dict[str, Any]] = {}
    
    async def create_batch_projects(
        self, 
        count: int, 
        genres: Optional[List[str]] = None,
        style: str = "comic"
    ) -> List[Dict[str, Any]]:
        """
        批量创建项目
        
        Args:
            count: 项目数量
            genres: 题材列表
            style: 风格
            
        Returns:
            项目列表
        """
        logger.info(f"开始批量创建项目: count={count}, genres={genres}")
        
        if not genres:
            genres = ["都市言情", "悬疑反转"]
        
        projects = []
        
        for i in range(count):
            try:
                # 轮询选择题材
                genre = genres[i % len(genres)]
                
                # 生成选题
                topic = await self.strategy.get_competitor_analysis(genre)
                
                # 创建项目
                project_id = str(uuid.uuid4())
                project = {
                    "id": project_id,
                    "title": f"批量项目_{i+1}_{genre}",
                    "genre": genre,
                    "style": style,
                    "status": "created",
                    "created_at": datetime.utcnow().isoformat()
                }
                
                projects.append(project)
                
                logger.info(f"创建项目 {i+1}/{count}: {project_id}")
                
            except Exception as e:
                logger.error(f"创建项目 {i+1} 失败: {e}")
        
        logger.info(f"批量创建项目完成: {len(projects)}/{count}")
        
        return projects
    
    async def generate_batch_videos(
        self, 
        projects: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        批量生成视频
        
        Args:
            projects: 项目列表
            progress_callback: 进度回调函数
            
        Returns:
            生成结果
        """
        logger.info(f"开始批量生成视频: projects={len(projects)}")
        
        total = len(projects)
        completed = 0
        failed = 0
        results = []
        
        # 创建任务ID
        batch_id = str(uuid.uuid4())
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def generate_single(project: Dict[str, Any]) -> Dict[str, Any]:
            """生成单个视频"""
            async with semaphore:
                try:
                    # 生成视频
                    result = await self.engine.full_pipeline(project["id"])
                    
                    completed += 1
                    
                    if progress_callback:
                        progress_callback(completed, total)
                    
                    logger.info(f"生成视频 {completed}/{total}: {project['id']}")
                    
                    return {
                        "project_id": project["id"],
                        "status": "completed",
                        "video_url": result.get("video_url"),
                        "error": None
                    }
                    
                except Exception as e:
                    failed += 1
                    
                    logger.error(f"生成视频失败 {project['id']}: {e}")
                    
                    return {
                        "project_id": project["id"],
                        "status": "failed",
                        "video_url": None,
                        "error": str(e)
                    }
        
        # 并发执行
        tasks = [generate_single(project) for project in projects]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                failed += 1
                logger.error(f"任务异常: {result}")
            else:
                valid_results.append(result)
        
        # 统计
        summary = {
            "batch_id": batch_id,
            "total": total,
            "completed": completed,
            "failed": failed,
            "success_rate": f"{completed/total*100:.1f}%" if total > 0 else "0%",
            "results": valid_results,
            "created_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"批量生成视频完成: {completed}/{total}, 失败: {failed}")
        
        return summary
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """获取批量状态"""
        return self.tasks.get(batch_id)
    
    def cancel_batch(self, batch_id: str) -> bool:
        """取消批量任务"""
        if batch_id in self.tasks:
            self.tasks[batch_id]["status"] = "cancelled"
            return True
        
        return False


class ProgressTracker:
    """进度追踪器"""
    
    def __init__(self):
        self.progress: Dict[str, Dict[str, Any]] = {}
    
    def start(self, task_id: str, total: int):
        """开始任务"""
        self.progress[task_id] = {
            "total": total,
            "completed": 0,
            "failed": 0,
            "status": "running",
            "start_time": datetime.utcnow().isoformat()
        }
    
    def update(self, task_id: str, completed: int, failed: int = 0):
        """更新进度"""
        if task_id in self.progress:
            self.progress[task_id]["completed"] = completed
            self.progress[task_id]["failed"] = failed
            self.progress[task_id]["progress"] = completed / self.progress[task_id]["total"]
    
    def complete(self, task_id: str):
        """完成任务"""
        if task_id in self.progress:
            self.progress[task_id]["status"] = "completed"
            self.progress[task_id]["end_time"] = datetime.utcnow().isoformat()
    
    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取进度"""
        return self.progress.get(task_id)


class BatchScheduler:
    """批量调度器"""
    
    def __init__(self):
        self.producer = BatchProducer()
        self.tracker = ProgressTracker()
    
    async def schedule_batch(
        self,
        count: int,
        genres: List[str],
        style: str = "comic",
        schedule_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        调度批量任务
        
        Args:
            count: 数量
            genres: 题材
            style: 风格
            schedule_time: 调度时间
            
        Returns:
            任务信息
        """
        task_id = str(uuid.uuid4())
        
        # 创建项目
        projects = await self.producer.create_batch_projects(count, genres, style)
        
        # 开始追踪
        self.tracker.start(task_id, len(projects))
        
        # 如果指定了调度时间,延迟执行
        if schedule_time:
            # TODO: 实现延迟调度
            pass
        
        # 执行批量生成
        result = await self.producer.generate_batch_videos(
            projects,
            progress_callback=lambda c, t: self.tracker.update(task_id, c, t - c)
        )
        
        # 完成追踪
        self.tracker.complete(task_id)
        
        return {
            "task_id": task_id,
            "projects": len(projects),
            "result": result
        }


class BatchValidator:
    """批量验证器"""
    
    @staticmethod
    def validate_batch_size(count: int) -> Dict[str, Any]:
        """验证批量大小"""
        result = {
            "valid": True,
            "warnings": []
        }
        
        if count <= 0:
            result["valid"] = False
            result["warnings"].append("数量必须大于0")
        
        if count > 100:
            result["warnings"].append("数量过大,建议分批处理")
        
        if count > 10:
            result["warnings"].append("并发数较高,注意API额度")
        
        return result
    
    @staticmethod
    def validate_genres(genres: List[str]) -> Dict[str, Any]:
        """验证题材"""
        valid_genres = ["都市言情", "悬疑反转", "家庭伦理", "玄幻修真"]
        
        result = {
            "valid": True,
            "warnings": []
        }
        
        for genre in genres:
            if genre not in valid_genres:
                result["warnings"].append(f"未知题材: {genre}")
        
        return result