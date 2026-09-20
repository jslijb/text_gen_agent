"""
视频合成服务 - 多段视频拼接、转场效果、字幕、BGM

功能:
1. 多段视频拼接（ffmpeg concat）
2. 转场效果（淡入淡出/切镜）
3. 字幕添加（SRT格式）
4. BGM添加（混音）
5. 完整合成流程：拼接→转场→字幕→BGM→输出
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

import imageio_ffmpeg

logger = logging.getLogger(__name__)

FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
logger.info(f"ffmpeg路径: {FFMPEG_BIN}")


def _run_ffmpeg(args: List[str], desc: str = "") -> bool:
    """执行ffmpeg命令"""
    cmd = [FFMPEG_BIN] + args + ["-y"]
    logger.info(f"执行 {desc}: {' '.join(cmd[:10])}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"ffmpeg失败: {result.stderr[-500:]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"ffmpeg超时: {desc}")
        return False
    except Exception as e:
        logger.error(f"ffmpeg异常: {e}")
        return False


def concat_videos(video_paths: List[str], output_path: str) -> bool:
    """拼接多个视频片段（无转场，直接连接）"""
    if not video_paths:
        return False
    if len(video_paths) == 1:
        Path(output_path).write_bytes(Path(video_paths[0]).read_bytes())
        return True

    list_file = Path(output_path).parent / "concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for vp in video_paths:
            f.write(f"file '{os.path.abspath(vp)}'\n")

    success = _run_ffmpeg([
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        output_path
    ], "拼接视频")

    list_file.unlink(missing_ok=True)
    return success


def _get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）"""
    try:
        result = subprocess.run(
            [FFMPEG_BIN, "-i", video_path, "-hide_banner"],
            capture_output=True, text=True, timeout=30
        )
        for line in result.stderr.split("\n"):
            if "Duration" in line:
                parts = line.strip().split("Duration: ")[1].split(",")[0]
                h, m, s = parts.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        pass
    return 5.0


def add_transition(video1: str, video2: str, output_path: str,
                   transition: str = "fade", duration: float = 0.5) -> bool:
    """两段视频间添加转场效果"""
    v1_duration = _get_video_duration(video1)
    offset = max(0, v1_duration - duration)
    filter_complex = (
        f"[0:v][1:v]xfade=transition={transition}:duration={duration}:offset={offset}[v]"
    )
    return _run_ffmpeg([
        "-i", video1,
        "-i", video2,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-c:a", "copy",
        output_path
    ], f"转场({transition})")


def concat_with_transitions(video_paths: List[str], output_path: str,
                            transition: str = "fade", duration: float = 0.5) -> bool:
    """多段视频带转场拼接"""
    if len(video_paths) <= 1:
        return concat_videos(video_paths, output_path)

    temp_dir = Path(output_path).parent / "temp_transitions"
    temp_dir.mkdir(exist_ok=True)

    current = video_paths[0]
    for i in range(1, len(video_paths)):
        temp_output = str(temp_dir / f"transition_{i}.mp4")
        if not add_transition(current, video_paths[i], temp_output, transition, duration):
            logger.warning(f"转场失败，回退直接拼接: {i}")
            return concat_videos(video_paths, output_path)
        current = temp_output

    Path(output_path).write_bytes(Path(current).read_bytes())

    for f in temp_dir.glob("*.mp4"):
        f.unlink()
    temp_dir.rmdir()
    return True


def create_srt_subtitle(shots: List[Dict[str, Any]], output_path: str):
    """创建SRT字幕文件"""
    cumulative_time = 0.0

    def format_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    lines = []
    for i, shot in enumerate(shots, 1):
        narration = shot.get("narration", "")
        if not narration:
            continue
        duration = shot.get("duration", 5)
        start = cumulative_time
        end = cumulative_time + duration
        cumulative_time = end

        lines.append(str(i))
        lines.append(f"{format_time(start)} --> {format_time(end)}")
        lines.append(narration)
        lines.append("")

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return output_path


def add_subtitle(video_path: str, srt_path: str, output_path: str) -> bool:
    """给视频添加字幕"""
    srt_abs = os.path.abspath(srt_path).replace("\\", "/").replace(":", "\\:")
    vf = f"subtitles='{srt_abs}':force_style='FontSize=24,FontName=Microsoft YaHei,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2'"
    return _run_ffmpeg([
        "-i", video_path,
        "-vf", vf,
        "-c:a", "copy",
        output_path
    ], "添加字幕")


def add_bgm(video_path: str, bgm_path: str, output_path: str,
            bgm_volume: float = 0.3) -> bool:
    """给视频添加背景音乐"""
    return _run_ffmpeg([
        "-i", video_path,
        "-i", bgm_path,
        "-filter_complex", f"[1:a]volume={bgm_volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[a]",
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac",
        output_path
    ], "添加BGM")


def compose_video(
    video_clips: List[str],
    shots: List[Dict[str, Any]],
    output_path: str,
    transition: str = "fade",
    transition_duration: float = 0.5,
    bgm_path: Optional[str] = None,
    bgm_volume: float = 0.3,
    add_subtitles: bool = True,
) -> Dict[str, Any]:
    """
    完整视频合成流程：
    1. 拼接视频片段（带转场）
    2. 添加字幕
    3. 添加BGM
    4. 输出最终视频

    Args:
        video_clips: 视频片段路径列表
        shots: 分镜信息列表（含narration, duration）
        output_path: 输出视频路径
        transition: 转场类型（fade/wipeleft/wiperight/slideup/slidedown）
        transition_duration: 转场时长（秒）
        bgm_path: BGM文件路径（可选）
        bgm_volume: BGM音量（0-1）
        add_subtitles: 是否添加字幕

    Returns:
        合成结果dict
    """
    result = {
        "success": False,
        "output_path": output_path,
        "steps": [],
        "total_duration": sum(s.get("duration", 5) for s in shots),
        "clip_count": len(video_clips),
    }

    temp_dir = Path(output_path).parent / "temp_compose"
    temp_dir.mkdir(exist_ok=True)

    step1_output = str(temp_dir / "step1_concat.mp4")
    if concat_with_transitions(video_clips, step1_output, transition, transition_duration):
        result["steps"].append("✅ 步骤1: 视频拼接+转场")
    else:
        result["steps"].append("❌ 步骤1: 视频拼接失败")
        return result
    current = step1_output

    if add_subtitles and shots:
        srt_path = str(temp_dir / "subtitle.srt")
        create_srt_subtitle(shots, srt_path)

        step2_output = str(temp_dir / "step2_subtitle.mp4")
        if add_subtitle(current, srt_path, step2_output):
            result["steps"].append("✅ 步骤2: 字幕添加")
            current = step2_output
        else:
            result["steps"].append("⚠️ 步骤2: 字幕添加失败，跳过")

    if bgm_path and os.path.exists(bgm_path):
        step3_output = str(temp_dir / "step3_bgm.mp4")
        if add_bgm(current, bgm_path, step3_output, bgm_volume):
            result["steps"].append("✅ 步骤3: BGM添加")
            current = step3_output
        else:
            result["steps"].append("⚠️ 步骤3: BGM添加失败，跳过")

    Path(output_path).write_bytes(Path(current).read_bytes())
    result["success"] = True
    result["file_size_mb"] = round(Path(output_path).stat().st_size / 1024 / 1024, 2)

    for f in temp_dir.glob("*"):
        f.unlink()
    temp_dir.rmdir()

    return result


def get_video_info(video_path: str) -> Dict[str, Any]:
    """获取视频信息（时长、分辨率等）"""
    cmd = [
        FFMPEG_BIN, "-i", video_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams"
    ]
    ffprobe_bin = FFMPEG_BIN.replace("ffmpeg", "ffprobe")
    cmd[0] = ffprobe_bin

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            format_info = data.get("format", {})
            streams = data.get("streams", [])
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})

            return {
                "duration": float(format_info.get("duration", 0)),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "codec": video_stream.get("codec_name", ""),
                "fps": eval(video_stream.get("r_frame_rate", "0/1")) if "r_frame_rate" in video_stream else 0,
            }
    except Exception as e:
        logger.error(f"获取视频信息失败: {e}")

    return {}