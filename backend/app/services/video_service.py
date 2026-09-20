import os
import time
import logging
import httpx
from app.config.settings import settings

logger = logging.getLogger(__name__)

# 平台 → Agnes 画面规格
# 注意：`aspect_ratio` 只在 mode=text 时主导画面比例；
#       mode=keyframe（图生视频）时成片比例**跟随 first_frame 图片本身**，
#       所以要出竖屏，首帧图必须先按 9:16 生成。
PLATFORM_PRESETS = {
    "douyin":   {"size": "720P", "aspect": "9:16", "out": "720x1280"},
    "kuaishou": {"size": "720P", "aspect": "9:16", "out": "720x1280"},
    "weishi":   {"size": "720P", "aspect": "9:16", "out": "720x1280"},
    "youku":    {"size": "720P", "aspect": "16:9", "out": "1280x720"},
    "iqiyi":    {"size": "720P", "aspect": "16:9", "out": "1280x720"},
    "tencent":  {"size": "720P", "aspect": "16:9", "out": "1280x720"},
}

# Agnes 有两套互不通用的端点 + key 空间，key 必须与域名配对（见 CLAUDE.md）：
#   https://api.agnes-ai.cn/v1      ← 配 sk-CioO…（backend/.env 当前值）
#   https://apihub.agnes-ai.com/v1  ← 配 sk-jY3Q…
# 401 的正确读法是「这把 key 不属于这个域名」。
AGNES_BASE_URL = os.getenv("AGNES_BASE_URL", "https://api.agnes-ai.cn/v1")
AGNES_VIDEO_MODEL = os.getenv("AGNES_VIDEO_MODEL", "agnes-video-2.5-flash")

# mode 合法值只有三个：text（文生视频）/ keyframe（首尾帧=图生视频）/ reference（参考）
VALID_MODES = ("text", "keyframe", "reference")


def _agnes_base_root(base_url: str) -> str:
    """把 .../v1 去掉，得到轮询接口所在的根地址"""
    return base_url.rstrip("/")[:-3] if base_url.rstrip("/").endswith("/v1") else base_url.rstrip("/")


class VideoService:
    def __init__(self):
        self.api_key = os.getenv("AGNES_KEY", "")
        self.base_url = AGNES_BASE_URL
        self.root_url = _agnes_base_root(AGNES_BASE_URL)
        self.status_url = f"{self.root_url}/agnesapi"
        self.model = AGNES_VIDEO_MODEL

    def create_video(self, prompt: str, image: str = None, platform: str = "douyin",
                     mode: str = None, seconds: int = 5, size: str = None,
                     aspect_ratio: str = None, image_urls: list = None) -> dict:
        """创建视频任务。

        Args:
            prompt: 画面描述
            image: 首帧图 URL（mode=keyframe 用，必须是**公网可访问**地址）
            platform: 目标平台（决定 size / aspect_ratio）
            mode: text / keyframe / reference，不传则按 image 有无自动判断
            seconds: 时长，合法范围 4–12（字符串或整数）
            size: 720P / 1080P / 1K / 2K（2.5-flash 只支持 720P）
            aspect_ratio: 画面比例，白名单 21:9 / 16:9 / 4:3 / 1:1 / 3:4 / 9:16
            image_urls: 参考图列表（mode=reference 用）
        """
        preset = PLATFORM_PRESETS.get(platform, PLATFORM_PRESETS["douyin"])
        size = size or preset["size"]
        aspect_ratio = aspect_ratio or preset["aspect"]

        if mode is None:
            mode = "keyframe" if image else ("reference" if image_urls else "text")
        if mode not in VALID_MODES:
            raise ValueError(f"非法 mode: {mode}，合法值 {VALID_MODES}")

        seconds = str(int(seconds))
        if not (4 <= int(seconds) <= 12):
            raise ValueError(f"seconds 必须在 4–12 之间，收到 {seconds}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "prompt": prompt,
            "mode": mode,               # ← 必填，旧代码完全没传
            "seconds": seconds,
            "size": size,
            "aspect_ratio": aspect_ratio,
        }

        # 图片字段随 mode 变化：keyframe 用 first_frame，reference 用 images。
        # 旧代码写的 payload["image"] 会直接被拒。
        if mode == "keyframe":
            if not image:
                raise ValueError("mode=keyframe 必须提供 first_frame（image 参数）")
            payload["first_frame"] = image
        elif mode == "reference":
            if not image_urls:
                raise ValueError("mode=reference 必须提供 images（image_urls 参数）")
            payload["images"] = image_urls

        logger.info(
            f"创建视频任务: model={self.model} mode={mode} seconds={seconds} "
            f"size={size} aspect={aspect_ratio} has_first_frame={bool(image)}"
        )

        response = httpx.post(
            f"{self.base_url}/videos",
            headers=headers,
            json=payload,
            timeout=120,
        )

        if response.status_code == 429:
            raise Exception("Agnes 免费档限流（429），需退避后重试")
        if response.status_code != 200:
            logger.error(f"视频任务创建失败: status={response.status_code}, body={response.text}")
            raise Exception(f"Agnes Video API 返回 {response.status_code}: {response.text}")

        result = response.json()
        logger.info(
            f"视频任务创建成功: video_id={result.get('video_id')}, "
            f"status={result.get('status')}"
        )
        return result

    def poll_video_status(self, video_id: str, max_wait: int = 900,
                          interval: int = 8) -> dict:
        """轮询任务直到完成。

        旧代码的两个坑：
          1) 没带 `model_name` —— 非 text 模式会查不到任务；
          2) 固定间隔不处理 429 —— 免费档会被反复掐死。
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}

        start = time.time()
        delay = interval
        while time.time() - start < max_wait:
            try:
                response = httpx.get(
                    self.status_url,
                    params={"video_id": video_id, "model_name": self.model},
                    headers=headers,
                    timeout=60,
                )
            except Exception as e:
                logger.warning(f"视频状态查询异常: {e}")
                time.sleep(delay)
                continue

            if response.status_code == 429:
                delay = min(delay * 2, 60)
                logger.warning(f"限流 429，退避 {delay}s")
                time.sleep(delay)
                continue

            if response.status_code != 200:
                logger.warning(f"视频状态查询失败: status={response.status_code}")
                time.sleep(delay)
                continue

            data = response.json()
            status = data.get("status", "unknown")
            logger.info(f"视频状态: video_id={video_id}, status={status}, "
                        f"progress={data.get('progress')}")

            if status == "completed":
                # 顶层 url 与 metadata.url 两处都可能给出产物地址
                url = data.get("url") or (data.get("metadata") or {}).get("url", "")
                if not url:
                    raise Exception(
                        f"任务已完成但未返回产物地址（video_id={video_id}）；"
                        f"可用 GET {self.base_url}/videos/{video_id}/content 重试取件"
                    )
                return {"status": "completed", "url": url}
            elif status == "failed":
                error = data.get("error", "Unknown error")
                raise Exception(f"视频生成失败: {error}")

            time.sleep(delay)

        raise TimeoutError(f"视频生成超时（{max_wait}秒）: video_id={video_id}")

    def fetch_video_bytes(self, video_id: str) -> bytes:
        """取件备用路径：网关直出 MP4 字节流。

        任务未完成时回 400「任务尚未完成」—— 那是正常门禁，不是接口坏。
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        r = httpx.get(f"{self.base_url}/videos/{video_id}/content",
                      headers=headers, timeout=300)
        if r.status_code != 200:
            raise Exception(f"取件失败 status={r.status_code}: {r.text[:200]}")
        if len(r.content) < 10240:
            raise Exception(f"取件内容异常（{len(r.content)} bytes）: {r.text[:200]}")
        return r.content

    def download_video(self, url: str, save_path: str) -> str:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        logger.info(f"下载视频: url={url}")
        response = httpx.get(url, timeout=300, follow_redirects=True)

        if response.status_code != 200:
            raise Exception(f"视频下载失败: status={response.status_code}")

        with open(save_path, "wb") as f:
            f.write(response.content)

        logger.info(f"视频下载完成: {save_path} ({len(response.content)} bytes)")
        return save_path
