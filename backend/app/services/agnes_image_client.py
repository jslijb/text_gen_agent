"""Agnes 图像 API 客户端（spec v1.4.0）

封装 Agnes 图像生成 API 调用，同步返回图片 URL。
API: POST https://apihub.agnes-ai.com/v1/images/generations
模型: agnes-image-2.1-flash
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

AGNES_IMAGE_URL = "https://apihub.agnes-ai.com/v1/images/generations"
AGNES_IMAGE_MODEL = "agnes-image-2.1-flash"
AGNES_IMAGE_TIMEOUT = 180  # 图像生成耗时较长，留足超时


class AgnesImageError(Exception):
    """Agnes 图像 API 调用异常"""


def generate_image(prompt: str, size: str = "768x1024") -> str:
    """
    调用 Agnes 图像 API 生成图片（同步返回）。

    Args:
        prompt: 文生图英文 prompt
        size: 图片尺寸，默认 768x1024（竖版封面 3:4）

    Returns:
        图片 URL（https://platform-outputs.agnes-ai.space/...）

    Raises:
        AgnesImageError: API 调用失败时抛出
    """
    api_key = os.getenv("AGNES_KEY", "")
    if not api_key:
        raise AgnesImageError("AGNES_KEY 环境变量未设置")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": AGNES_IMAGE_MODEL,
        "prompt": prompt,
        "size": size,
    }

    logger.info(f"调用 Agnes 图像 API: model={AGNES_IMAGE_MODEL}, size={size}, prompt_len={len(prompt)}")
    try:
        resp = requests.post(AGNES_IMAGE_URL, json=payload, headers=headers, timeout=AGNES_IMAGE_TIMEOUT)
    except requests.exceptions.Timeout:
        raise AgnesImageError(f"Agnes 图像 API 超时（{AGNES_IMAGE_TIMEOUT}s）")
    except requests.exceptions.RequestException as e:
        raise AgnesImageError(f"Agnes 图像 API 请求失败: {e}")

    if resp.status_code != 200:
        raise AgnesImageError(f"Agnes 图像 API 返回 {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
    except ValueError as e:
        raise AgnesImageError(f"Agnes 图像 API 响应解析失败: {e}")

    images = data.get("data", [])
    if not images:
        raise AgnesImageError(f"Agnes 图像 API 返回空 data: {data}")

    img_url = images[0].get("url")
    if not img_url:
        raise AgnesImageError(f"Agnes 图像 API 返回无 url: {images[0]}")

    logger.info(f"Agnes 图像 API 成功: {img_url}")
    return img_url
