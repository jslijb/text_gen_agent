"""
真实API端到端测试 - 验证三个key对应的视频模型

测试内容:
1. Agnes API (AGNES_KEY) 生成视频
2. 阿里百炼标准API (DASHSCOPE_API_KEY1) 9个视频模型
3. 阿里百炼Token Plan (DASHSCOPE_TOKEN_KEY) 3个模型
4. 快手平台合规检查
5. 爆款特征融入验证

注意: 此测试调用真实API，会产生费用，请确保:
1. 配置了正确的API Key (backend/.env)
2. 有足够的额度
3. 网络连接正常

运行方式:
    conda activate bigmodel
    cd backend
    pytest tests/test_e2e_real_api.py -v -s --tb=long
"""

import os
import sys
import time
import json
import asyncio
import logging
import httpx
import pytest
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).parent.parent
ENV_FILE = BACKEND_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


VIRAL_FEATURES = {
    "hook_first_3s": ["震惊", "意外", "竟然", "真相", "原来", "突然", "没想到"],
    "title_suspense_words": ["真相揭晓", "意外发现", "结局反转", "竟然", "原来", "没想到"],
    "title_emotion_words": ["虐心", "高甜", "泪目", "震惊", "可怕", "暖心"],
    "title_genre_words": ["重生", "穿越", "霸总", "复仇", "逆袭", "豪门"],
    "ending_suspense": ["下集", "续集", "未完", "待续", "关注", "敬请期待"],
    "shot_duration_range": (2, 5),
    "total_duration_range": (15, 60),
    "title_length_range": (17, 30),
}

KUAISHOU_SPEC = {
    "duration_range": (15, 180),
    "supported_resolutions": ["720p", "1080p", "1280x720", "1920x1080", "768x1344", "1080x1920"],
    "aspect_ratio": "9:16",
    "format": "mp4",
    "fps": 30,
}


def _build_viral_test_case() -> Dict[str, Any]:
    """构建融入爆款特征的测试用例（基于对标账号调研）"""
    return {
        "topic": {
            "title": "重生回19岁她竟然做了这个震惊决定#短剧#",
            "genre": "都市言情",
            "style": "comic",
            "target_duration": 30,
            "reason": "重生题材热度高,开头钩子强,符合爆款特征",
        },
        "script": {
            "title": "重生回19岁她竟然做了这个震惊决定#短剧#",
            "content": "重生回19岁，看着熟悉的教室，她竟然做了一个让所有人震惊的决定...",
            "shots": [
                {
                    "sequence": 1,
                    "description": "女主角在教室震惊醒来的特写",
                    "narration": "震惊！重生回19岁，她竟然回到了高考前",
                    "duration": 5,
                    "image_prompt": "漫画风格，女主角震惊表情特写，教室背景，阳光从窗户照入，高清，竖屏9:16",
                    "video_prompt": "镜头从黑板快速推进到女主角脸部特写，震惊表情，漫画风格，竖屏9:16，30fps",
                    "transition": "淡入",
                },
                {
                    "sequence": 2,
                    "description": "女主角回忆前世的中景",
                    "narration": "前世的遗憾，这一次竟然可以避免",
                    "duration": 5,
                    "image_prompt": "漫画风格，女主角回忆前世画面，中景，高清，竖屏9:16",
                    "video_prompt": "镜头缓慢推近，女主角回忆画面闪回，漫画风格，竖屏9:16，30fps",
                    "transition": "切镜",
                },
                {
                    "sequence": 3,
                    "description": "女主角坚定眼神的中景",
                    "narration": "这一次，她竟然不会再重蹈覆辙",
                    "duration": 5,
                    "image_prompt": "漫画风格，女主角坚定的眼神，教室背景，中景，高清，竖屏9:16",
                    "video_prompt": "镜头缓慢平移，女主角坚定眼神，漫画风格，竖屏9:16，30fps",
                    "transition": "切镜",
                },
                {
                    "sequence": 4,
                    "description": "女主角走出教室的背影",
                    "narration": "关注我，下集更精彩！第1/10集",
                    "duration": 5,
                    "image_prompt": "漫画风格，女主角走出教室的背影，走廊，阳光，高清，竖屏9:16",
                    "video_prompt": "镜头跟随女主角走出教室，背影，漫画风格，竖屏9:16，30fps",
                    "transition": "淡出",
                },
            ],
        },
    }


def _check_viral_features(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """检查测试用例是否融入爆款特征"""
    result = {"valid": True, "checks": [], "score": 0}
    score = 0
    total_checks = 6

    title = test_case["script"]["title"]
    title_len = len(title)
    if VIRAL_FEATURES["title_length_range"][0] <= title_len <= VIRAL_FEATURES["title_length_range"][1]:
        result["checks"].append(f"✅ 标题长度合规: {title_len}字")
        score += 1
    else:
        result["checks"].append(f"❌ 标题长度不合规: {title_len}字(建议17-30字)")
        result["valid"] = False

    has_suspense = any(w in title for w in VIRAL_FEATURES["title_suspense_words"])
    if has_suspense:
        result["checks"].append("✅ 标题包含悬念词")
        score += 1
    else:
        result["checks"].append("❌ 标题缺少悬念词")
        result["valid"] = False

    has_emotion = any(w in title for w in VIRAL_FEATURES["title_emotion_words"])
    if has_emotion:
        result["checks"].append("✅ 标题包含情绪词")
        score += 1
    else:
        result["checks"].append("⚠️ 标题缺少情绪词(建议添加)")

    shots = test_case["script"]["shots"]
    if shots:
        first_narration = shots[0]["narration"][:20]
        has_hook = any(w in first_narration for w in VIRAL_FEATURES["hook_first_3s"])
        if has_hook:
            result["checks"].append("✅ 开头3秒有钩子")
            score += 1
        else:
            result["checks"].append("❌ 开头3秒缺少钩子")
            result["valid"] = False

        last_narration = shots[-1]["narration"][-20:]
        has_ending = any(w in last_narration for w in VIRAL_FEATURES["ending_suspense"])
        if has_ending:
            result["checks"].append("✅ 结尾有悬念引导追更")
            score += 1
        else:
            result["checks"].append("❌ 结尾缺少悬念引导")
            result["valid"] = False

    total_duration = sum(s["duration"] for s in shots)
    dur_range = VIRAL_FEATURES["total_duration_range"]
    if dur_range[0] <= total_duration <= dur_range[1]:
        result["checks"].append(f"✅ 总时长合规: {total_duration}秒")
        score += 1
    else:
        result["checks"].append(f"❌ 总时长不合规: {total_duration}秒(建议{dur_range[0]}-{dur_range[1]}秒)")
        result["valid"] = False

    result["score"] = round(score / total_checks * 100, 1)
    return result


def _check_kuaishou_compliance(video_url: str, duration: Optional[int] = None) -> Dict[str, Any]:
    """检查视频是否符合快手平台规范"""
    result = {"valid": True, "checks": [], "score": 0}
    score = 0
    total_checks = 3

    if video_url and video_url.startswith("http"):
        result["checks"].append("✅ 视频URL有效")
        score += 1
    else:
        result["checks"].append(f"❌ 视频URL无效: {video_url}")
        result["valid"] = False

    if video_url and ".mp4" in video_url.lower():
        result["checks"].append("✅ 视频格式为MP4")
        score += 1
    else:
        result["checks"].append("⚠️ 视频格式未知(非MP4 URL)")

    if duration is not None:
        dur_range = KUAISHOU_SPEC["duration_range"]
        if dur_range[0] <= duration <= dur_range[1]:
            result["checks"].append(f"✅ 视频时长合规: {duration}秒")
            score += 1
        else:
            result["checks"].append(f"❌ 视频时长不合规: {duration}秒(建议{dur_range[0]}-{dur_range[1]}秒)")
            result["valid"] = False
    else:
        result["checks"].append("⚠️ 视频时长未知(API未返回)")
        score += 1

    result["score"] = round(score / total_checks * 100, 1)
    return result


class E2ETestReport:
    """端到端测试报告生成器"""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.start_time = datetime.now()

    def add_result(self, provider: str, model: str, api_key_env: str,
                   success: bool, video_url: str = "", duration: Optional[int] = None,
                   error: str = "", compliance: Optional[Dict] = None,
                   viral: Optional[Dict] = None, response_time: float = 0):
        self.results.append({
            "provider": provider,
            "model": model,
            "api_key_env": api_key_env,
            "success": success,
            "video_url": video_url,
            "duration": duration,
            "error": error,
            "compliance": compliance,
            "viral": viral,
            "response_time": response_time,
        })

    def save(self, filepath: Path):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        total = len(self.results)
        success_count = sum(1 for r in self.results if r["success"])
        fail_count = total - success_count

        lines = []
        lines.append("# 真实API端到端测试报告")
        lines.append("")
        lines.append(f"**测试时间**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**耗时**: {elapsed:.1f}秒")
        lines.append(f"**测试总数**: {total}")
        lines.append(f"**成功**: {success_count}")
        lines.append(f"**失败**: {fail_count}")
        lines.append(f"**成功率**: {success_count/total*100:.1f}%" if total > 0 else "**成功率**: N/A")
        lines.append("")
        lines.append("## 测试结果汇总")
        lines.append("")
        lines.append("| 序号 | 提供商 | 模型 | Key | 状态 | 耗时 | 视频URL | 合规分 | 爆款分 |")
        lines.append("|------|--------|------|-----|------|------|---------|--------|--------|")
        for i, r in enumerate(self.results, 1):
            status = "✅ 成功" if r["success"] else "❌ 失败"
            url_display = r["video_url"][:50] + "..." if r["video_url"] and len(r["video_url"]) > 50 else (r["video_url"] or "-")
            comp_score = r["compliance"]["score"] if r["compliance"] else "-"
            viral_score = r["viral"]["score"] if r["viral"] else "-"
            lines.append(f"| {i} | {r['provider']} | {r['model']} | {r['api_key_env']} | {status} | {r['response_time']:.1f}s | {url_display} | {comp_score} | {viral_score} |")
        lines.append("")
        lines.append("## 详细测试结果")
        lines.append("")
        for i, r in enumerate(self.results, 1):
            lines.append(f"### {i}. {r['provider']} - {r['model']}")
            lines.append("")
            lines.append(f"- **API Key**: `{r['api_key_env']}`")
            lines.append(f"- **状态**: {'✅ 成功' if r['success'] else '❌ 失败'}")
            lines.append(f"- **耗时**: {r['response_time']:.1f}秒")
            if r["video_url"]:
                lines.append(f"- **视频URL**: {r['video_url']}")
            if r["duration"]:
                lines.append(f"- **视频时长**: {r['duration']}秒")
            if r["error"]:
                lines.append(f"- **错误信息**: {r['error']}")
            if r["compliance"]:
                lines.append(f"- **快手合规检查** (得分: {r['compliance']['score']}):")
                for check in r["compliance"]["checks"]:
                    lines.append(f"  - {check}")
            if r["viral"]:
                lines.append(f"- **爆款特征检查** (得分: {r['viral']['score']}):")
                for check in r["viral"]["checks"]:
                    lines.append(f"  - {check}")
            lines.append("")
        lines.append("## 踩坑记录")
        lines.append("")
        failed = [r for r in self.results if not r["success"]]
        if failed:
            for r in failed:
                lines.append(f"- **{r['model']}**: {r['error']}")
        else:
            lines.append("- 无失败记录")
        lines.append("")
        lines.append("---")
        lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        filepath.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"测试报告已保存: {filepath}")


report = E2ETestReport()
test_case = _build_viral_test_case()
viral_check = _check_viral_features(test_case)


async def _call_agnes_video_api(prompt: str, image: Optional[str] = None) -> Tuple[bool, str, Optional[int], str]:
    """调用Agnes视频生成API"""
    api_key = os.getenv("AGNES_KEY", "")
    if not api_key or api_key == "your_token_plan_key_here":
        return False, "", None, "AGNES_KEY未配置"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "agnes-video-v2.0",
        "prompt": prompt,
        "num_frames": 121,
        "frame_rate": 24,
        "width": 768,
        "height": 1344,
    }
    if image:
        payload["image"] = image

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post("https://api.agnes-ai.cn/v1/videos", headers=headers, json=payload)
        if resp.status_code == 403:
            return False, "", None, "403 Forbidden - 额度用完"
        if resp.status_code != 200:
            return False, "", None, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        video_id = data.get("video_id") or data.get("id")
        if not video_id:
            url = data.get("url") or data.get("video_url")
            if url:
                return True, url, None, ""
            return False, "", None, f"响应无video_id: {json.dumps(data)[:200]}"

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
                        status = poll_data.get("status", "unknown")
                        if status == "completed" or status == "success":
                            url = poll_data.get("metadata", {}).get("url") or poll_data.get("url")
                            duration = poll_data.get("metadata", {}).get("duration")
                            return True, url or "", duration, ""
                        elif status == "failed" or status == "error":
                            return False, "", None, f"视频生成失败: {poll_data.get('error', 'unknown')}"
                except Exception as e:
                    logger.warning(f"轮询异常: {e}")
                await asyncio.sleep(10)
        return False, "", None, "视频生成超时(10分钟)"
    except Exception as e:
        return False, "", None, str(e)


async def _call_dashscope_video_api(model_id: str, prompt: str, image: Optional[str] = None) -> Tuple[bool, str, Optional[int], str]:
    """调用阿里百炼标准API视频生成"""
    api_key = os.getenv("DASHSCOPE_API_KEY1", "")
    if not api_key:
        return False, "", None, "DASHSCOPE_API_KEY1未配置"

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
            "duration": 5,
            "prompt_extend": True,
            "watermark": False,
        },
    }
    if image:
        payload["input"]["image"] = image

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis",
                headers=headers,
                json=payload,
            )
        if resp.status_code == 403:
            return False, "", None, "403 Forbidden - 额度用完"
        if resp.status_code != 200:
            return False, "", None, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        output = data.get("output", {})
        task_id = output.get("task_id")
        task_status = output.get("task_status", "")

        if task_status == "SUCCEEDED":
            url = output.get("video_url", "")
            return True, url, None, ""

        if task_id:
            max_wait = 600
            start = time.time()
            async with httpx.AsyncClient(timeout=30) as client:
                while time.time() - start < max_wait:
                    try:
                        poll_resp = await client.get(
                            f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                            headers={"Authorization": f"Bearer {api_key}"},
                        )
                        if poll_resp.status_code == 200:
                            poll_data = poll_resp.json()
                            task_status = poll_data.get("output", {}).get("task_status", "")
                            if task_status == "SUCCEEDED":
                                video_url = poll_data.get("output", {}).get("video_url", "")
                                usage = poll_data.get("usage", {})
                                duration = usage.get("output_video_duration") or usage.get("duration")
                                return True, video_url, duration, ""
                            elif task_status == "FAILED":
                                err_msg = poll_data.get("output", {}).get("message", "unknown")
                                return False, "", None, f"任务失败: {err_msg}"
                            logger.info(f"轮询中... 状态: {task_status}")
                    except Exception as e:
                        logger.warning(f"轮询异常: {e}")
                    await asyncio.sleep(15)
            return False, "", None, "视频生成超时(10分钟)"

        return False, "", None, f"响应无task_id: {json.dumps(data)[:200]}"
    except Exception as e:
        return False, "", None, str(e)


async def _call_token_plan_video_api(model_id: str, prompt: str, image: Optional[str] = None) -> Tuple[bool, str, Optional[int], str]:
    """调用阿里百炼Token Plan视频生成"""
    api_key = os.getenv("DASHSCOPE_TOKEN_KEY", "")
    if not api_key or api_key == "your_token_plan_key_here":
        return False, "", None, "DASHSCOPE_TOKEN_KEY未配置(占位符)"

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
            "duration": 5,
            "prompt_extend": True,
            "watermark": False,
        },
    }
    if image:
        payload["input"]["image"] = image

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis",
                headers=headers,
                json=payload,
            )
        if resp.status_code == 401:
            return False, "", None, "401 Unauthorized - Token Key不匹配"
        if resp.status_code == 403:
            return False, "", None, "403 Forbidden - 额度用完"
        if resp.status_code != 200:
            return False, "", None, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        output = data.get("output", {})
        task_id = output.get("task_id")
        task_status = output.get("task_status", "")

        if task_status == "SUCCEEDED":
            url = output.get("video_url", "")
            return True, url, None, ""

        if task_id:
            max_wait = 600
            start = time.time()
            async with httpx.AsyncClient(timeout=30) as client:
                while time.time() - start < max_wait:
                    try:
                        poll_resp = await client.get(
                            f"https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1/tasks/{task_id}",
                            headers={"Authorization": f"Bearer {api_key}"},
                        )
                        if poll_resp.status_code == 200:
                            poll_data = poll_resp.json()
                            task_status = poll_data.get("output", {}).get("task_status", "")
                            if task_status == "SUCCEEDED":
                                video_url = poll_data.get("output", {}).get("video_url", "")
                                usage = poll_data.get("usage", {})
                                duration = usage.get("output_video_duration") or usage.get("duration")
                                return True, video_url, duration, ""
                            elif task_status == "FAILED":
                                err_msg = poll_data.get("output", {}).get("message", "unknown")
                                return False, "", None, f"任务失败: {err_msg}"
                            logger.info(f"轮询中... 状态: {task_status}")
                    except Exception as e:
                        logger.warning(f"轮询异常: {e}")
                    await asyncio.sleep(15)
            return False, "", None, "视频生成超时(10分钟)"

        return False, "", None, f"响应无task_id: {json.dumps(data)[:200]}"
    except Exception as e:
        return False, "", None, str(e)


DASHSCOPE_MODELS = [
    "wan2.7-t2v-2026-06-12",
    "wan2.7-r2v-2026-06-12",
    "qwen-image-3.0",
    "happyhorse-1.1-r2v",
    "happyhorse-1.1-t2v",
    "wan3.0-video",
    "qwen-image-3.0-pro",
    "happyhorse-1.1-i2v",
    "qwen-image-2.0-pro-2026-06-22",
]

TOKEN_PLAN_MODELS = [
    "happyhorse-1.1-t2v",
    "happyhorse-1.1-i2v",
    "happyhorse-1.1-r2v",
]


# ============ 测试用例 ============

class TestE2EViralFeatures:
    """爆款特征验证测试"""

    @pytest.mark.e2e
    def test_viral_features_in_test_case(self):
        """验证测试用例融入了爆款特征"""
        assert viral_check["valid"], f"测试用例未满足爆款特征: {viral_check['checks']}"
        assert viral_check["score"] >= 80, f"爆款特征得分过低: {viral_check['score']}"

    @pytest.mark.e2e
    def test_title_length(self):
        """验证标题长度17-30字"""
        title = test_case["script"]["title"]
        assert 17 <= len(title) <= 30, f"标题长度{len(title)}不在17-30范围内"

    @pytest.mark.e2e
    def test_hook_in_first_3s(self):
        """验证开头3秒有钩子"""
        first_narration = test_case["script"]["shots"][0]["narration"][:20]
        has_hook = any(w in first_narration for w in VIRAL_FEATURES["hook_first_3s"])
        assert has_hook, "开头3秒缺少钩子词"

    @pytest.mark.e2e
    def test_suspense_in_ending(self):
        """验证结尾有悬念引导追更"""
        last_narration = test_case["script"]["shots"][-1]["narration"][-20:]
        has_ending = any(w in last_narration for w in VIRAL_FEATURES["ending_suspense"])
        assert has_ending, "结尾缺少悬念引导"


class TestE2EAgnesAPI:
    """Agnes API (AGNES_KEY) 端到端测试"""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_agnes_video_generation(self):
        """测试Agnes API生成视频"""
        prompt = test_case["script"]["shots"][0]["video_prompt"]
        start = time.time()
        success, video_url, duration, error = await _call_agnes_video_api(prompt)
        elapsed = time.time() - start

        compliance = _check_kuaishou_compliance(video_url, duration) if success else None

        report.add_result(
            provider="Agnes",
            model="agnes-video-v2.0",
            api_key_env="AGNES_KEY",
            success=success,
            video_url=video_url,
            duration=duration,
            error=error,
            compliance=compliance,
            viral=viral_check,
            response_time=elapsed,
        )

        if success:
            logger.info(f"✅ Agnes API测试成功: {video_url}")
        else:
            logger.warning(f"❌ Agnes API测试失败: {error}")

        assert success, f"Agnes API生成视频失败: {error}"


class TestE2EDashscopeAPI:
    """阿里百炼标准API (DASHSCOPE_API_KEY1) 端到端测试"""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.parametrize("model_id", DASHSCOPE_MODELS)
    async def test_dashscope_model(self, model_id):
        """测试百炼标准API各模型"""
        prompt = test_case["script"]["shots"][0]["video_prompt"]
        start = time.time()
        success, video_url, duration, error = await _call_dashscope_video_api(model_id, prompt)
        elapsed = time.time() - start

        compliance = _check_kuaishou_compliance(video_url, duration) if success else None

        report.add_result(
            provider="DashScope",
            model=model_id,
            api_key_env="DASHSCOPE_API_KEY1",
            success=success,
            video_url=video_url,
            duration=duration,
            error=error,
            compliance=compliance,
            viral=viral_check,
            response_time=elapsed,
        )

        if success:
            logger.info(f"✅ DashScope {model_id} 测试成功: {video_url}")
        else:
            logger.warning(f"❌ DashScope {model_id} 测试失败: {error}")

        assert success, f"DashScope {model_id} 生成视频失败: {error}"


class TestE2ETokenPlanAPI:
    """阿里百炼Token Plan (DASHSCOPE_TOKEN_KEY) 端到端测试"""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.parametrize("model_id", TOKEN_PLAN_MODELS)
    async def test_token_plan_model(self, model_id):
        """测试Token Plan各模型"""
        prompt = test_case["script"]["shots"][0]["video_prompt"]
        start = time.time()
        success, video_url, duration, error = await _call_token_plan_video_api(model_id, prompt)
        elapsed = time.time() - start

        compliance = _check_kuaishou_compliance(video_url, duration) if success else None

        report.add_result(
            provider="TokenPlan",
            model=model_id,
            api_key_env="DASHSCOPE_TOKEN_KEY",
            success=success,
            video_url=video_url,
            duration=duration,
            error=error,
            compliance=compliance,
            viral=viral_check,
            response_time=elapsed,
        )

        if success:
            logger.info(f"✅ TokenPlan {model_id} 测试成功: {video_url}")
        else:
            logger.warning(f"❌ TokenPlan {model_id} 测试失败: {error}")

        assert success, f"TokenPlan {model_id} 生成视频失败: {error}"


class TestE2EReportGeneration:
    """测试报告生成"""

    @pytest.mark.e2e
    def test_generate_report(self):
        """生成端到端测试报告"""
        report_path = REPORTS_DIR / f"e2e_real_api_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report.save(report_path)
        assert report_path.exists(), "测试报告未生成"

        latest_path = REPORTS_DIR / "e2e_real_api_report.md"
        report.save(latest_path)
        assert latest_path.exists(), "最新测试报告未生成"

        logger.info(f"测试报告已生成: {latest_path}")


def pytest_sessionfinish(session, exitstatus):
    """pytest会话结束时自动保存报告"""
    report_path = REPORTS_DIR / "e2e_real_api_report.md"
    report.save(report_path)