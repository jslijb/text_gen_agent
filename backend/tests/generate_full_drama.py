"""
多段视频生成脚本 - 生成1-2分钟完整AI漫剧

流程:
1. 定义AI漫剧剧本（融入爆款特征）
2. 拆分为多个镜头（每个5-10秒）
3. 并行调用百炼API生成每个镜头视频
4. 用video_composer合成完整视频（拼接+转场+字幕）

运行方式:
    conda activate bigmodel
    cd backend
    python tests/generate_full_drama.py
"""

import os
import sys
import time
import json
import asyncio
import logging
import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
from services.video_composer import compose_video, get_video_info, concat_videos

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).parent.parent
ENV_FILE = BACKEND_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

VIDEOS_DIR = BACKEND_DIR / "app" / "static" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR = VIDEOS_DIR / "temp_clips"
TEMP_DIR.mkdir(exist_ok=True)


def build_drama_script() -> Dict[str, Any]:
    """构建完整AI漫剧剧本（融入爆款特征，1-2分钟）"""
    return {
        "title": "重生回19岁她竟然做了这个震惊决定#短剧#",
        "genre": "都市言情",
        "style": "comic",
        "target_duration": 90,
        "shots": [
            {
                "sequence": 1,
                "description": "女主角在教室震惊醒来的特写",
                "narration": "震惊！重生回19岁，她竟然回到了高考前",
                "duration": 5,
                "video_prompt": "漫画风格，镜头从黑板快速推进到女主角脸部特写，震惊表情，教室背景，阳光从窗户照入，高清，竖屏9:16，30fps",
            },
            {
                "sequence": 2,
                "description": "女主角回忆前世被欺负的画面",
                "narration": "前世的屈辱，这一次竟然可以避免",
                "duration": 5,
                "video_prompt": "漫画风格，女主角回忆前世画面闪回，被欺负的场景，中景，高清，竖屏9:16，30fps",
            },
            {
                "sequence": 3,
                "description": "女主角坚定眼神的中景",
                "narration": "这一次，她竟然不会再重蹈覆辙",
                "duration": 5,
                "video_prompt": "漫画风格，女主角坚定的眼神，教室背景，中景，高清，竖屏9:16，30fps",
            },
            {
                "sequence": 4,
                "description": "女主角走到校霸面前的近景",
                "narration": "校霸看着她，没想到她竟然敢反抗",
                "duration": 5,
                "video_prompt": "漫画风格，女主角走到校霸面前，对峙场景，近景，高清，竖屏9:16，30fps",
            },
            {
                "sequence": 5,
                "description": "女主角反击的动态画面",
                "narration": "她竟然一巴掌扇了过去，所有人都震惊了",
                "duration": 5,
                "video_prompt": "漫画风格，女主角反击扇巴掌的动态画面，慢动作，高清，竖屏9:16，30fps",
            },
            {
                "sequence": 6,
                "description": "周围同学震惊表情的群像",
                "narration": "全班同学都震惊了，没想到乖乖女竟然变了",
                "duration": 5,
                "video_prompt": "漫画风格，周围同学震惊表情的群像，全景，高清，竖屏9:16，30fps",
            },
            {
                "sequence": 7,
                "description": "男主角在窗外注视的特写",
                "narration": "窗外的他，竟然露出了意味深长的笑",
                "duration": 5,
                "video_prompt": "漫画风格，英俊男主角在窗外注视的特写，意味深长的微笑，高清，竖屏9:16，30fps",
            },
            {
                "sequence": 8,
                "description": "女主角自信走出校门的全景",
                "narration": "从今天起，她的人生竟然完全不同了",
                "duration": 5,
                "video_prompt": "漫画风格，女主角自信走出校门的全景，阳光明媚，高清，竖屏9:16，30fps",
            },
            {
                "sequence": 9,
                "description": "女主角和男主角对视的中景",
                "narration": "而他，竟然一直在等她",
                "duration": 5,
                "video_prompt": "漫画风格，女主角和英俊男主角对视的中景，暧昧氛围，高清，竖屏9:16，30fps",
            },
            {
                "sequence": 10,
                "description": "女主角背影走向远方的远景",
                "narration": "关注我，下集更精彩！第1/10集",
                "duration": 5,
                "video_prompt": "漫画风格，女主角背影走向远方的远景，夕阳，高清，竖屏9:16，30fps",
            },
        ],
    }


async def generate_clip_agnes(
    prompt: str,
    api_key: str,
    clip_index: int,
) -> Tuple[int, bool, str, str]:
    """
    用Agnes API生成单个视频片段

    Returns: (clip_index, success, video_url, error)
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "agnes-video-v2.0",
        "prompt": prompt,
        "num_frames": 121,
        "frame_rate": 24,
        "width": 768,
        "height": 1344,
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post("https://api.agnes-ai.cn/v1/videos", headers=headers, json=payload)
        if resp.status_code != 200:
            return clip_index, False, "", f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        video_id = data.get("video_id") or data.get("id")
        if not video_id:
            return clip_index, False, "", f"无video_id: {json.dumps(data)[:200]}"

        max_wait = 600
        start = time.time()
        async with httpx.AsyncClient(timeout=30) as client:
            while time.time() - start < max_wait:
                try:
                    poll_resp = await client.get(
                        f"https://api.agnes-ai.cn/agnesapi?video_id={video_id}",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    if poll_resp.status_code == 200:
                        poll_data = poll_resp.json()
                        status = poll_data.get("status", poll_data.get("internal_status", ""))
                        if status in ("completed", "success"):
                            url = poll_data.get("metadata", {}).get("url") or poll_data.get("url")
                            return clip_index, True, url or "", ""
                        elif status in ("failed", "error"):
                            err = poll_data.get("error", "unknown")
                            return clip_index, False, "", f"视频生成失败: {err}"
                except Exception as e:
                    logger.warning(f"镜头{clip_index} 轮询异常: {e}")
                await asyncio.sleep(10)
        return clip_index, False, "", "超时(10分钟)"
    except Exception as e:
        return clip_index, False, "", str(e)


async def generate_clip(
    prompt: str,
    model_id: str,
    api_key: str,
    base_url: str,
    clip_index: int,
    duration: int = 5,
) -> Tuple[int, bool, str, str]:
    """
    生成单个视频片段（DashScope/Token Plan）

    Returns: (clip_index, success, video_url, error)
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    payload = {
        "model": model_id,
        "input": {"prompt": prompt},
        "parameters": {
            "resolution": "720P",
            "ratio": "9:16",
            "duration": duration,
            "prompt_extend": True,
            "watermark": False,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{base_url}/api/v1/services/aigc/video-generation/video-synthesis",
                headers=headers,
                json=payload,
            )
        if resp.status_code != 200:
            return clip_index, False, "", f"HTTP {resp.status_code}: {resp.text[:200]}"

        data = resp.json()
        output = data.get("output", {})
        task_id = output.get("task_id")
        task_status = output.get("task_status", "")

        if task_status == "SUCCEEDED":
            return clip_index, True, output.get("video_url", ""), ""

        if task_id:
            max_wait = 600
            start = time.time()
            async with httpx.AsyncClient(timeout=30) as client:
                while time.time() - start < max_wait:
                    try:
                        poll_resp = await client.get(
                            f"{base_url}/api/v1/tasks/{task_id}",
                            headers={"Authorization": f"Bearer {api_key}"},
                        )
                        if poll_resp.status_code == 200:
                            poll_data = poll_resp.json()
                            task_status = poll_data.get("output", {}).get("task_status", "")
                            if task_status == "SUCCEEDED":
                                url = poll_data.get("output", {}).get("video_url", "")
                                return clip_index, True, url, ""
                            elif task_status == "FAILED":
                                err = poll_data.get("output", {}).get("message", "unknown")
                                return clip_index, False, "", f"任务失败: {err}"
                    except Exception as e:
                        logger.warning(f"镜头{clip_index} 轮询异常: {e}")
                    await asyncio.sleep(15)
            return clip_index, False, "", "超时(10分钟)"

        return clip_index, False, "", f"无task_id: {json.dumps(data)[:200]}"
    except Exception as e:
        return clip_index, False, "", str(e)


async def download_video(url: str, filepath: str, max_retries: int = 5) -> bool:
    """下载视频到本地（带重试）"""
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    Path(filepath).write_bytes(resp.content)
                    return True
                logger.warning(f"下载尝试{attempt+1}失败: HTTP {resp.status_code}, 大小 {len(resp.content)}")
        except Exception as e:
            logger.warning(f"下载尝试{attempt+1}异常: {e}")
        if attempt < max_retries - 1:
            await asyncio.sleep(10)
    logger.error(f"下载最终失败({max_retries}次重试): {url[:80]}")
    return False


async def generate_full_drama(
    script: Dict[str, Any],
    model_id: str = "agnes-video-v2.0",
    api_key_env: str = "AGNES_KEY",
    base_url: str = "",
    provider: str = "agnes",
) -> Dict[str, Any]:
    """
    生成完整AI漫剧

    1. 逐个生成所有镜头视频
    2. 下载所有视频片段
    3. 合成完整视频（拼接+转场+字幕）
    """
    result = {
        "title": script["title"],
        "model": model_id,
        "api_key_env": api_key_env,
        "provider": provider,
        "start_time": datetime.now().isoformat(),
        "shots": [],
        "clip_paths": [],
        "success": False,
    }

    api_key = os.getenv(api_key_env, "")
    if not api_key:
        result["error"] = f"{api_key_env}未配置"
        return result

    shots = script["shots"]
    total_duration = sum(s["duration"] for s in shots)
    logger.info(f"=== 开始生成AI漫剧 ===")
    logger.info(f"标题: {script['title']}")
    logger.info(f"镜头数: {len(shots)}")
    logger.info(f"目标时长: {total_duration}秒")
    logger.info(f"模型: {model_id} ({api_key_env}) Provider: {provider}")

    logger.info(f"\n--- 步骤1: 逐个生成{len(shots)}个镜头 ---")
    start_time = time.time()

    WAIT_BETWEEN = 10
    clip_results = []
    for i, shot in enumerate(shots):
        logger.info(f"  生成镜头 {shot['sequence']}/{len(shots)}")

        if provider == "agnes":
            clip_result = await generate_clip_agnes(
                shot["video_prompt"],
                api_key,
                shot["sequence"],
            )
        else:
            clip_result = await generate_clip(
                shot["video_prompt"],
                model_id,
                api_key,
                base_url,
                shot["sequence"],
                shot["duration"],
            )
        clip_results.append(clip_result)

        if i < len(shots) - 1:
            logger.info(f"    等待{WAIT_BETWEEN}秒...")
            await asyncio.sleep(WAIT_BETWEEN)

    gen_elapsed = time.time() - start_time
    success_count = sum(1 for r in clip_results if r[1])
    logger.info(f"生成完成: {success_count}/{len(shots)} 成功, 耗时 {gen_elapsed:.1f}秒")

    for idx, success, url, error in clip_results:
        shot_result = {
            "sequence": idx,
            "success": success,
            "url": url,
            "error": error,
        }
        result["shots"].append(shot_result)
        status = "✅" if success else "❌"
        logger.info(f"  镜头{idx}: {status} {'生成成功' if success else error[:50]}")

    if success_count < len(shots):
        logger.warning(f"有{len(shots) - success_count}个镜头生成失败，将仅合成成功的镜头")

    successful_clips = [(idx, url) for idx, success, url, _ in clip_results if success]
    if not successful_clips:
        result["error"] = "所有镜头生成失败"
        return result

    logger.info(f"\n--- 步骤2: 逐个下载{len(successful_clips)}个视频片段 ---")
    clip_paths = []
    for idx, url in successful_clips:
        filepath = str(TEMP_DIR / f"clip_{idx}.mp4")
        success = await download_video(url, filepath)
        if success and Path(filepath).exists():
            clip_paths.append((idx, filepath))
            size_mb = Path(filepath).stat().st_size / 1024 / 1024
            logger.info(f"  镜头{idx}: ✅ 下载成功 ({size_mb:.2f} MB)")
        else:
            logger.warning(f"  镜头{idx}: ❌ 下载失败")
        await asyncio.sleep(2)

    if not clip_paths:
        result["error"] = "所有视频下载失败"
        return result

    logger.info(f"\n--- 步骤3: 合成完整视频 ---")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"full_drama_{model_id}_{timestamp}.mp4"
    output_path = str(VIDEOS_DIR / output_filename)

    sorted_clip_paths = [p for _, p in sorted(clip_paths)]
    successful_shots = [shots[idx - 1] for idx, _ in sorted(clip_paths)]

    compose_result = compose_video(
        video_clips=sorted_clip_paths,
        shots=successful_shots,
        output_path=output_path,
        transition="fade",
        transition_duration=0.5,
        add_subtitles=True,
    )

    result["compose"] = compose_result
    result["output_path"] = output_path
    result["output_filename"] = output_filename
    result["generation_time"] = round(gen_elapsed, 1)
    result["total_time"] = round(time.time() - start_time, 1)
    result["success"] = compose_result["success"]
    result["end_time"] = datetime.now().isoformat()

    if compose_result["success"]:
        for f in TEMP_DIR.glob("*.mp4"):
            f.unlink()

    if compose_result["success"]:
        logger.info(f"\n=== 合成成功! ===")
        logger.info(f"输出文件: {output_path}")
        logger.info(f"文件大小: {compose_result.get('file_size_mb', 0)} MB")
        logger.info(f"总耗时: {result['total_time']}秒")
        for step in compose_result["steps"]:
            logger.info(f"  {step}")

        video_info = get_video_info(output_path)
        if video_info:
            logger.info(f"视频信息: {video_info.get('duration', 0):.1f}秒, "
                        f"{video_info.get('width', 0)}x{video_info.get('height', 0)}, "
                        f"{video_info.get('codec', '')}")
            result["video_info"] = video_info
    else:
        logger.error(f"合成失败: {compose_result.get('steps', [])}")

    return result


async def main():
    """主函数：生成完整AI漫剧"""
    script = build_drama_script()

    result = await generate_full_drama(
        script=script,
        model_id="agnes-video-v2.0",
        api_key_env="AGNES_KEY",
        provider="agnes",
    )

    report_path = VIDEOS_DIR.parent / "reports" / f"full_drama_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.parent.mkdir(exist_ok=True)

    lines = ["# AI漫剧生成报告", ""]
    lines.append(f"**生成时间**: {result.get('start_time', '')}")
    lines.append(f"**标题**: {result.get('title', '')}")
    lines.append(f"**模型**: {result.get('model', '')} ({result.get('api_key_env', '')})")
    lines.append(f"**状态**: {'✅ 成功' if result.get('success') else '❌ 失败'}")
    lines.append(f"**生成耗时**: {result.get('generation_time', 0)}秒")
    lines.append(f"**总耗时**: {result.get('total_time', 0)}秒")
    lines.append("")

    if result.get("output_path"):
        lines.append(f"**输出文件**: `{result['output_path']}`")
    if result.get("compose", {}).get("file_size_mb"):
        lines.append(f"**文件大小**: {result['compose']['file_size_mb']} MB")
    if result.get("video_info"):
        vi = result["video_info"]
        lines.append(f"**视频信息**: {vi.get('duration', 0):.1f}秒, {vi.get('width', 0)}x{vi.get('height', 0)}")
    lines.append("")

    lines.append("## 镜头生成结果")
    lines.append("")
    lines.append("| 镜头 | 状态 | 说明 |")
    lines.append("|------|------|------|")
    for shot in result.get("shots", []):
        status = "✅" if shot["success"] else "❌"
        desc = shot.get("url", "")[:50] if shot["success"] else shot.get("error", "")[:50]
        lines.append(f"| {shot['sequence']} | {status} | {desc} |")
    lines.append("")

    if result.get("compose"):
        lines.append("## 合成步骤")
        lines.append("")
        for step in result["compose"].get("steps", []):
            lines.append(f"- {step}")
        lines.append("")

    if result.get("error"):
        lines.append(f"## 错误信息\n\n{result['error']}")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"\n报告已保存: {report_path}")

    return result


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result.get("success") else 1)