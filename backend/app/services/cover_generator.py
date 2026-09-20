import logging
import os
import time

import httpx

from app.services.model_manager import ModelManager
from app.config.settings import settings

logger = logging.getLogger(__name__)

# ---- Agnes 图像接口（实测可用：返回 COS 公开直链，可直接下载）----
AGNES_DEFAULT_BASE = "https://api.agnes-ai.cn/v1"
AGNES_IMAGE_MODELS = [
    "agnes-image-2.5-flash",
    "agnes-image-2.1-flash",
    "agnes-image-2.0-flash",
]
# Agnes 图像接口支持的 size 为「宽x高」字符串
AGNES_IMAGE_SIZE = "768x1024"

# ---- 百炼文生图：必须走**原生异步接口** ----
# ⚠️ 图像生成模型不能走 /compatible-mode 的文本 Base URL（会 400 / 静默降级）。
DASHSCOPE_T2I_SUBMIT = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
)
DASHSCOPE_TASK_TPL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
DASHSCOPE_IMAGE_MODELS = ["wan2.6-t2i", "wan2.5-t2i-preview"]


class CoverGenerator:
    def __init__(self):
        self.model_manager = ModelManager()

    def generate_cover_prompt(self, title: str, genre: str, synopsis: str) -> str:
        prompt = self.model_manager.call_llm(
            prompt=f"""请为以下小说生成一个封面图的英文提示词（用于AI绘图），要求简洁、有视觉冲击力：

小说标题：{title}
题材：{genre}
简介：{synopsis[:200]}

请直接输出英文提示词，不要解释。提示词应包含：主体、风格、色调、氛围。""",
            role="planner",
            system_prompt="你是一位专业的AI绘图提示词工程师，擅长为小说封面创作视觉描述。",
            temperature=0.8,
            max_tokens=200,
        )
        return prompt.strip()

    def generate_cover_with_api(self, title: str, genre: str, synopsis: str) -> str:
        prompt = self.generate_cover_prompt(title, genre, synopsis)
        # 第一优先级 Agnes 图像（实测可用、免费），第二优先 百炼原生文生图
        for name, fn in (("Agnes", self._generate_with_agnes),
                         ("百炼", self._generate_with_dashscope)):
            try:
                path = fn(prompt, title)
                if path:
                    logger.info(f"{name} 封面生成成功: {path}")
                    return path
            except Exception as e:
                logger.warning(f"{name} 生成封面失败: {e}")
        logger.error("图像接口均不可用，降级为文字封面")
        return self._generate_text_cover(title, genre, synopsis)

    def _save_remote_image(self, url: str, title: str) -> str:
        """下载远端图像到本地并返回静态路径"""
        r = httpx.get(url, timeout=180, follow_redirects=True)
        if r.status_code != 200:
            raise RuntimeError(f"图像下载失败 status={r.status_code}")
        if len(r.content) < 10240:
            raise RuntimeError(f"图像内容过小 {len(r.content)} bytes")
        os.makedirs(settings.COVERS_DIR, exist_ok=True)
        cover_path = os.path.join(settings.COVERS_DIR, f"{title}_cover.png")
        with open(cover_path, "wb") as f:
            f.write(r.content)
        return f"/static/covers/{title}_cover.png"

    def _generate_with_agnes(self, prompt: str, title: str) -> str:
        """Agnes 图像接口（与 models.yaml 的 image_generator 角色一致）"""
        key = os.getenv("AGNES_KEY", "")
        if not key:
            raise ValueError("AGNES_KEY 未配置")
        base = os.getenv("AGNES_BASE_URL", AGNES_DEFAULT_BASE).rstrip("/")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        last = ""
        for model in AGNES_IMAGE_MODELS:
            try:
                resp = httpx.post(
                    f"{base}/images/generations",
                    headers=headers,
                    json={"model": model, "prompt": prompt, "size": AGNES_IMAGE_SIZE},
                    timeout=300,
                )
                if resp.status_code != 200:
                    last = f"{model} -> {resp.status_code} {resp.text[:150]}"
                    continue
                url = resp.json()["data"][0]["url"]
                return self._save_remote_image(url, title)
            except Exception as e:
                last = f"{model} -> {type(e).__name__}: {e}"
        raise RuntimeError(last or "Agnes 图像生成全部失败")

    def _generate_with_dashscope(self, prompt: str, title: str) -> str:
        """百炼文生图 —— 原生异步接口（提交 → 轮询 → 取图）"""
        key = os.getenv("DASHSCOPE_API_KEY1", "")
        if not key:
            raise ValueError("DASHSCOPE_API_KEY1 未配置")
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",      # 异步调用必须
        }
        last = ""
        for model in DASHSCOPE_IMAGE_MODELS:
            try:
                submit = httpx.post(
                    DASHSCOPE_T2I_SUBMIT,
                    headers=headers,
                    json={
                        "model": model,
                        "input": {"prompt": prompt},
                        "parameters": {"size": "768*1024", "n": 1},
                    },
                    timeout=60,
                )
                if submit.status_code != 200:
                    last = f"{model} 提交失败 {submit.status_code} {submit.text[:150]}"
                    continue
                task_id = (submit.json().get("output") or {}).get("task_id")
                if not task_id:
                    last = f"{model} 无 task_id: {submit.text[:150]}"
                    continue

                url = None
                for _ in range(60):
                    time.sleep(5)
                    q = httpx.get(
                        DASHSCOPE_TASK_TPL.format(task_id=task_id),
                        headers={"Authorization": f"Bearer {key}"},
                        timeout=30,
                    )
                    if q.status_code != 200:
                        continue
                    output = q.json().get("output") or {}
                    status = output.get("task_status")
                    if status == "SUCCEEDED":
                        url = self._extract_image_url(output)
                        break
                    if status == "FAILED":
                        last = f"{model} 任务失败: {str(output)[:200]}"
                        break
                if url:
                    return self._save_remote_image(url, title)
            except Exception as e:
                last = f"{model} -> {type(e).__name__}: {e}"
        raise RuntimeError(last or "百炼文生图全部失败")

    @staticmethod
    def _extract_image_url(output: dict) -> str:
        """兼容两种响应格式"""
        for r in (output.get("results") or []):
            if r.get("url"):
                return r["url"]
        for c in (output.get("choices") or []):
            for part in ((c.get("message") or {}).get("content") or []):
                if part.get("image"):
                    return part["image"]
        return ""

    def _generate_text_cover(self, title: str, genre: str, synopsis: str) -> str:
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new("RGB", (512, 768), color=(15, 15, 30))
            draw = ImageDraw.Draw(img)
            genre_colors = {
                "都市情感": (99, 102, 241), "悬疑推理": (139, 92, 246),
                "重生逆袭": (245, 158, 11), "甜宠虐恋": (236, 72, 153),
                "古言宫斗": (180, 83, 9), "玄幻仙侠": (34, 211, 238),
                "科幻": (6, 182, 212), "其他": (107, 114, 128),
            }
            accent = genre_colors.get(genre, (99, 102, 241))
            draw.rectangle([0, 0, 512, 8], fill=accent)
            draw.rectangle([0, 760, 512, 768], fill=accent)
            draw.rectangle([40, 200, 472, 202], fill=accent)
            try:
                font_title = ImageFont.truetype("msyh.ttc", 42)
                font_genre = ImageFont.truetype("msyh.ttc", 20)
                font_synopsis = ImageFont.truetype("msyh.ttc", 16)
            except Exception:
                font_title = ImageFont.load_default()
                font_genre = font_title
                font_synopsis = font_title
            lines = [title[i:i+8] for i in range(0, len(title), 8)]
            y = 100
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font_title)
                x = (512 - (bbox[2] - bbox[0])) // 2
                draw.text((x, y), line, fill=(232, 232, 240), font=font_title)
                y += 55
            draw.text((40, 220), genre, fill=accent, font=font_genre)
            short_synopsis = synopsis[:80] + "..." if len(synopsis) > 80 else synopsis
            y = 280
            for i in range(0, len(short_synopsis), 20):
                draw.text((40, y), short_synopsis[i:i+20], fill=(136, 136, 160), font=font_synopsis)
                y += 24
            cover_path = os.path.join(settings.COVERS_DIR, f"{title}_cover.png")
            os.makedirs(settings.COVERS_DIR, exist_ok=True)
            img.save(cover_path)
            logger.info(f"文字封面已生成: {cover_path}")
            return f"/static/covers/{title}_cover.png"
        except Exception as e:
            logger.error(f"文字封面生成失败: {e}")
            return ""