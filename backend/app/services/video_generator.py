"""
视频生成模块

功能:
- 支持多模型:Agnes → DASHSCOPE_API_KEY1 → DASHSCOPE_TOKEN_KEY
- 支持403自动切换和黑名单机制
- 支持文生视频(T2V)、图生视频(I2V)、参考生视频(R2V)
- 视频片段合并
"""

import asyncio
import logging
import os
import subprocess
import uuid
import time
import httpx
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from app.services.model_manager import ModelManager
from app.config.prompts.prompt_loader import load_prompt
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Agnes 视频模型与端点（key 必须与域名配对，见 CLAUDE.md）
AGNES_BASE_URL = os.getenv("AGNES_BASE_URL", "https://api.agnes-ai.cn/v1").rstrip("/")
AGNES_ROOT_URL = AGNES_BASE_URL[:-3] if AGNES_BASE_URL.endswith("/v1") else AGNES_BASE_URL
AGNES_VIDEO_MODEL = os.getenv("AGNES_VIDEO_MODEL", "agnes-video-2.5-flash")
AGNES_SECONDS = "6"          # 合法范围 4–12
AGNES_SIZE = "720P"          # 2.5-flash 只支持 720P
AGNES_ASPECT = "9:16"        # 竖屏；注意 keyframe 模式下成片比例跟随首帧图

FFMPEG_BIN = None


def _ffmpeg() -> str:
    """惰性获取 ffmpeg 可执行文件（优先 imageio-ffmpeg 自带的静态版本）"""
    global FFMPEG_BIN
    if FFMPEG_BIN:
        return FFMPEG_BIN
    import shutil
    try:
        import imageio_ffmpeg
        FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG_BIN = shutil.which("ffmpeg") or "ffmpeg"
    return FFMPEG_BIN



class VideoProvider(str, Enum):
    """视频提供商"""
    AGNES = "agnes"
    DASHSCOPE = "dashscope"
    TOKEN_PLAN = "token_plan"


class VideoGenerator:
    """视频生成器"""
    
    def __init__(self):
        self.model_manager = ModelManager()
        self.prompt_template = load_prompt("video.yaml", "video_generation")
        self.videos_dir = os.path.join(settings.STATIC_DIR, "videos")
        os.makedirs(self.videos_dir, exist_ok=True)
        
        # 黑名单(403错误的模型)
        self.blacklist: set = set()
        
        # 当前使用的模型
        self.current_model: Optional[str] = None
        self.current_provider: Optional[VideoProvider] = None
    
    async def generate(
        self, 
        project_id: str, 
        shots: List[Dict[str, Any]], 
        assets: List[Dict[str, Any]]
    ) -> str:
        """
        生成视频
        
        Args:
            project_id: 项目ID
            shots: 分镜列表
            assets: 素材列表
            
        Returns:
            最终视频URL
        """
        logger.info(f"开始生成视频: project_id={project_id}, shots={len(shots)}")
        
        video_clips = []
        
        for i, shot in enumerate(shots):
            try:
                # 获取对应的素材
                asset = self._find_asset_for_shot(assets, i)
                
                # 生成视频片段
                video_clip = await self._generate_clip(project_id, shot, asset, i)
                
                if video_clip:
                    video_clips.append(video_clip)
                    logger.info(f"生成视频片段 {i+1}/{len(shots)} 成功")
                else:
                    logger.warning(f"生成视频片段 {i+1}/{len(shots)} 失败")
                    
            except Exception as e:
                logger.error(f"生成视频片段 {i+1} 失败: {e}")
        
        if not video_clips:
            raise Exception("所有视频片段生成失败")
        
        # 合并视频片段
        final_video = await self._concat_videos(video_clips, project_id)
        
        logger.info(f"视频生成完成: {final_video}")
        
        return final_video
    
    async def _generate_clip(
        self, 
        project_id: str, 
        shot: Dict[str, Any], 
        asset: Optional[Dict[str, Any]], 
        index: int
    ) -> Optional[str]:
        """
        生成视频片段
        
        按优先级尝试不同模型:
        1. Agnes API (免费)
        2. DASHSCOPE_API_KEY1 (10个模型)
        3. DASHSCOPE_TOKEN_KEY (3个Token Plan模型)
        """
        # 第一优先级: Agnes API
        try:
            if AGNES_VIDEO_MODEL not in self.blacklist:
                result = await self._generate_with_agnes(project_id, shot, asset, index)
                if result:
                    self.current_model = AGNES_VIDEO_MODEL
                    self.current_provider = VideoProvider.AGNES
                    return result
        except Exception as e:
            logger.warning(f"Agnes生成失败: {e}")
            if "403" in str(e):
                self.blacklist.add(AGNES_VIDEO_MODEL)
                logger.info("Agnes已加入黑名单")
        
        # 第二优先级: DASHSCOPE_API_KEY1
        # 2026-09-15 实测排序（合法参数提交验证，产物已落盘核对）：
        #   wan3.0-video / -prime: /video-synthesis 端点，5s 720x1280 30fps AAC，
        #     支持 duration 2~30s、9:16 原生竖屏、默认带音轨
        #   wan2.7-r2v: reference_image 保持角色/画风（实测成立）
        #   happyhorse-1.1-*: /generation 端点，24fps，免费档日额度撞墙 429
        #   注：qwen-image 系列是图像模型，不进视频降级链
        dashscope_models = [
            "wan3.0-video",
            "wan3.0-video-prime",
            "wan2.7-r2v-2026-06-12",
            "happyhorse-1.1-i2v",
            "happyhorse-1.1-t2v",
            "happyhorse-1.1-r2v",
        ]
        
        for model_id in dashscope_models:
            try:
                if model_id in self.blacklist:
                    continue
                    
                result = await self._generate_with_dashscope(
                    project_id, shot, asset, index, model_id
                )
                if result:
                    self.current_model = model_id
                    self.current_provider = VideoProvider.DASHSCOPE
                    return result
            except Exception as e:
                logger.warning(f"{model_id}生成失败: {e}")
                if "403" in str(e):
                    self.blacklist.add(model_id)
                    logger.info(f"{model_id}已加入黑名单")
        
        # 第三优先级: DASHSCOPE_TOKEN_KEY
        token_plan_models = [
            "happyhorse-1.1-t2v",
            "happyhorse-1.1-i2v",
            "happyhorse-1.1-r2v"
        ]
        
        for model_id in token_plan_models:
            try:
                if model_id in self.blacklist:
                    continue
                    
                result = await self._generate_with_token_plan(
                    project_id, shot, asset, index, model_id
                )
                if result:
                    self.current_model = model_id
                    self.current_provider = VideoProvider.TOKEN_PLAN
                    return result
            except Exception as e:
                logger.warning(f"{model_id}(Token Plan)生成失败: {e}")
                if "403" in str(e):
                    self.blacklist.add(model_id)
                    logger.info(f"{model_id}已加入黑名单")
        
        raise Exception("所有视频生成模型都不可用")
    
    async def _generate_with_agnes(
        self,
        project_id: str,
        shot: Dict[str, Any],
        asset: Optional[Dict[str, Any]],
        index: int
    ) -> str:
        """使用Agnes API生成视频

        有素材图 → mode=keyframe（首帧控制，= 图生视频）
        无素材图 → mode=text（文生视频）

        ⚠️ 图片字段是 `first_frame`，不是 `image`；`mode` 是必填项。
        ⚠️ 首帧图必须是**公网可访问**的 URL（本地文件传不进去）。
        """
        api_key = os.getenv("AGNES_KEY", "")

        if not api_key:
            raise ValueError("AGNES_KEY未配置")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        image_url = (asset or {}).get("image_url")
        mode = "keyframe" if image_url else "text"

        payload = {
            "model": AGNES_VIDEO_MODEL,
            "prompt": shot.get("video_prompt", ""),
            "mode": mode,
            "seconds": AGNES_SECONDS,
            "size": AGNES_SIZE,
            "aspect_ratio": AGNES_ASPECT,
        }
        if image_url:
            payload["first_frame"] = image_url

        response = httpx.post(
            f"{AGNES_BASE_URL}/videos",
            headers=headers,
            json=payload,
            timeout=120
        )

        if response.status_code == 429:
            raise Exception("Agnes 免费档限流（429），需退避后重试")
        if response.status_code == 403:
            raise Exception("403 Forbidden - 额度用完")
        if response.status_code != 200:
            raise Exception(f"Agnes API返回 {response.status_code}: {response.text}")

        result = response.json()
        video_id = result.get("video_id") or result.get("id") or result.get("task_id")
        if not video_id:
            raise Exception(f"Agnes 未返回 video_id: {str(result)[:200]}")

        video_url = await self._poll_agnes_status(video_id, api_key)

        return video_url

    async def _poll_agnes_status(self, video_id: str, api_key: str) -> str:
        """轮询Agnes视频状态

        ⚠️ 非 text 模式**必须**带 `model_name`，否则查不到任务（旧代码漏了）。
        """
        headers = {
            "Authorization": f"Bearer {api_key}"
        }

        max_wait = 1500   # 免费档排队 + 生成，25 分钟兜底
        delay = 8

        start = time.time()
        while time.time() - start < max_wait:
            try:
                response = httpx.get(
                    f"{AGNES_ROOT_URL}/agnesapi",
                    params={"video_id": video_id, "model_name": AGNES_VIDEO_MODEL},
                    headers=headers,
                    timeout=60
                )
            except Exception as e:
                logger.warning(f"Agnes 状态查询异常: {e}")
                await asyncio.sleep(delay)
                continue

            if response.status_code == 429:
                delay = min(delay * 2, 60)
                logger.warning(f"Agnes 限流 429，退避 {delay}s")
                await asyncio.sleep(delay)
                continue

            if response.status_code != 200:
                await asyncio.sleep(delay)
                continue

            data = response.json()
            status = data.get("status", "unknown")
            logger.info(f"Agnes视频状态: video_id={video_id}, status={status}, "
                        f"progress={data.get('progress')}")

            if status == "completed":
                # 顶层 url 与 metadata.url 两处都可能给出产物地址
                url = data.get("url") or (data.get("metadata") or {}).get("url", "")
                if not url:
                    raise Exception(
                        f"Agnes 任务已完成但未返回产物地址（video_id={video_id}）；"
                        f"可改用 GET {AGNES_BASE_URL}/videos/{video_id}/content 取件"
                    )
                return url
            elif status == "failed":
                raise Exception(f"视频生成失败: {data.get('error')}")

            await asyncio.sleep(delay)

        raise TimeoutError(f"Agnes 视频生成超时: video_id={video_id}")
    
    async def _generate_with_dashscope(
        self,
        project_id: str,
        shot: Dict[str, Any],
        asset: Optional[Dict[str, Any]],
        index: int,
        model_id: str
    ) -> str:
        """使用阿里百炼标准API生成视频

        2026-09-15 按实测重写（此前走 /compatible-mode/v1/videos 是不存在的端点）：
        - 端点: POST /api/v1/services/aigc/video-generation/video-synthesis
          （wan3.0/wan2.7 系）；happyhorse 系走 .../generation
        - 请求体: input.prompt / input.media[{type,url}] / parameters
        - 异步任务: 提交拿 task_id -> 轮询 /api/v1/tasks/{task_id}
          -> SUCCEEDED 后 output.video_url（OSS 直链，24 小时有效，需及时下载）
        """
        api_key = os.getenv("DASHSCOPE_API_KEY1", "")

        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY1未配置")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

        endpoint = (
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/generation"
            if model_id.startswith("happyhorse")
            else "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
        )

        input_body: Dict[str, Any] = {"prompt": shot.get("video_prompt", "")}
        if asset and asset.get("image_url"):
            input_body["media"] = [{"type": "first_frame", "url": asset["image_url"]}]

        payload = {
            "model": model_id,
            "input": input_body,
            "parameters": {
                "resolution": "720P",
                "ratio": "9:16",
                "duration": 5,
            },
        }

        response = httpx.post(endpoint, headers=headers, json=payload, timeout=60)

        if response.status_code != 200:
            raise Exception(
                f"DashScope API返回 {response.status_code}: {response.text[:300]}"
            )

        task_id = response.json().get("output", {}).get("task_id", "")
        if not task_id:
            raise Exception(f"DashScope 未返回 task_id: {response.text[:300]}")

        # 轮询任务（免费/低档位生成约 1-3 分钟）
        poll_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        deadline = time.time() + 600
        while time.time() < deadline:
            await asyncio.sleep(10)
            poll = httpx.get(
                poll_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
            if poll.status_code != 200:
                continue
            out = poll.json().get("output", {})
            status = out.get("task_status")
            if status == "SUCCEEDED":
                video_url = out.get("video_url", "")
                if not video_url:
                    raise Exception("任务成功但 video_url 为空")
                return video_url
            if status in ("FAILED", "CANCELED", "UNKNOWN"):
                raise Exception(f"视频任务失败: {poll.text[:300]}")

        raise TimeoutError(f"视频任务超时: task_id={task_id}")
    
    async def _generate_with_token_plan(
        self,
        project_id: str,
        shot: Dict[str, Any],
        asset: Optional[Dict[str, Any]],
        index: int,
        model_id: str
    ) -> str:
        """使用阿里百炼Token Plan生成视频"""
        api_key = os.getenv("DASHSCOPE_TOKEN_KEY", "")
        
        if not api_key:
            raise ValueError("DASHSCOPE_TOKEN_KEY未配置")
        
        # 构建请求(Anthropic兼容模式)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": model_id,
            "prompt": shot.get("video_prompt", "")
        }
        
        # 如果有图像,使用图生视频
        if asset and asset.get("image_url"):
            payload["image"] = asset["image_url"]
        
        # 调用API
        response = httpx.post(
            "https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic/v1/messages",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 403:
            raise Exception("403 Forbidden - 额度用完")
        
        if response.status_code != 200:
            raise Exception(f"Token Plan API返回 {response.status_code}: {response.text}")
        
        result = response.json()
        
        return result.get("url", "")
    
    def _find_asset_for_shot(
        self, 
        assets: List[Dict[str, Any]], 
        shot_index: int
    ) -> Optional[Dict[str, Any]]:
        """查找分镜对应的素材"""
        for asset in assets:
            if asset.get("metadata", {}).get("shot_id") == shot_index:
                return asset
        
        # 如果没有精确匹配,返回第一个素材
        if assets:
            return assets[0]
        
        return None
    
    async def _concat_videos(self, video_urls: List[str], project_id: str) -> str:
        """把多个短片合并成一条完整视频。

        为什么需要这一步：单个镜头受模型时长上限约束（Agnes `seconds` 上限 12），
        一条剧情/解说视频必然是多段拼起来的。

        做法：
          1) 各片段先统一下载到本地；
          2) **必须重编码**再用 concat 拼接 —— 直接用 `-c copy` 会因为各段
             SPS/PPS、时间基、音轨参数不一致而产生花屏或音画不同步；
          3) concat demuxer 需要绝对路径（Windows 反斜杠要转正斜杠）。
        """
        if not video_urls:
            raise Exception("没有可合并的视频片段")

        work_dir = os.path.join(self.videos_dir, f"concat_{project_id}_{uuid.uuid4().hex[:8]}")
        os.makedirs(work_dir, exist_ok=True)

        local_clips: List[str] = []
        for i, url in enumerate(video_urls):
            dst = os.path.join(work_dir, f"seg_{i:03d}.mp4")
            try:
                r = httpx.get(url, timeout=300, follow_redirects=True)
                if r.status_code != 200 or len(r.content) < 10240:
                    logger.warning(f"片段 {i+1} 下载异常（status={r.status_code}, "
                                   f"{len(r.content)} bytes），跳过")
                    continue
                with open(dst, "wb") as f:
                    f.write(r.content)
                local_clips.append(dst)
            except Exception as e:
                logger.error(f"片段 {i+1} 下载失败: {e}")

        if not local_clips:
            raise Exception("所有片段都下载失败，无法合并")
        if len(local_clips) == 1:
            logger.warning("只有 1 个片段，无需合并")
            return video_urls[0]

        list_file = os.path.join(work_dir, "concat.txt")
        with open(list_file, "w", encoding="utf-8") as f:
            f.write("\n".join("file '%s'" % p.replace("\\", "/") for p in local_clips))

        out_path = os.path.join(self.videos_dir, f"{project_id}_final.mp4")
        cmd = [
            _ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", list_file,
            "-c:v", "libx264", "-preset", "medium", "-crf", "21",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-ar", "44100", "-ac", "2", "-movflags", "+faststart", out_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="ignore")
        if proc.returncode != 0:
            raise Exception(f"视频合并失败: {proc.stderr[-600:]}")

        logger.info(f"视频合并完成: {len(local_clips)} 段 -> {out_path}")
        return out_path
    
    def get_blacklist(self) -> List[str]:
        """获取黑名单"""
        return list(self.blacklist)
    
    def clear_blacklist(self):
        """清空黑名单"""
        self.blacklist.clear()
        logger.info("黑名单已清空")
    
    def get_current_model(self) -> Optional[str]:
        """获取当前使用的模型"""
        return self.current_model
    
    def get_current_provider(self) -> Optional[VideoProvider]:
        """获取当前提供商"""
        return self.current_provider


class VideoQualityChecker:
    """视频质量检查器"""
    
    @staticmethod
    def check_video(video_url: str) -> Dict[str, Any]:
        """检查视频质量"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "score": 100
        }
        
        # 检查URL是否有效
        if not video_url or not video_url.startswith("http"):
            result["errors"].append("无效的视频URL")
            result["valid"] = False
            result["score"] -= 50
        
        return result
    
    @staticmethod
    def check_videos(video_urls: List[str]) -> Dict[str, Any]:
        """检查视频列表质量"""
        result = {
            "valid": True,
            "errors": [],
            "total_score": 0,
            "average_score": 0
        }
        
        if not video_urls:
            result["errors"].append("视频列表为空")
            result["valid"] = False
            return result
        
        # 检查每个视频
        total_score = 0
        for i, video_url in enumerate(video_urls):
            video_result = VideoQualityChecker.check_video(video_url)
            total_score += video_result["score"]
            
            if not video_result["valid"]:
                result["errors"].append(f"第{i+1}个视频: {video_result['errors']}")
        
        result["total_score"] = total_score
        result["average_score"] = total_score / len(video_urls)
        
        if result["average_score"] < 60:
            result["valid"] = False
        
        return result