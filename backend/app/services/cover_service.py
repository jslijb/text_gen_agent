"""小说封面生成服务（spec 5.8 / design 1.3.8，v1.4.0 改造：Agnes 图像 API）

流程：
1. Agnes LLM（agnes-2.0-flash, role=cover_planner）编排英文画面描述（降级到固定模板）
2. 调用 Agnes 图像 API（agnes-image-2.1-flash）同步文生图
3. 下载图片到本地 static/covers/
4. Pillow 叠加书名文字（AI 图像模型无法可靠生成中文，改为后期叠加）
5. 返回 cover_url
"""
import logging
import os
import time

import requests

# 模块级导入（便于测试 mock）
from app.services.model_manager import ModelManager
from app.services.agnes_image_client import generate_image, AgnesImageError
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Agnes 图像模型
AGNES_IMAGE_MODEL = "agnes-image-2.1-flash"
IMAGE_SIZE = "768x1024"  # 竖版书封面比例 3:4

# LLM 编排画面描述 Prompt 模板（spec v1.4.0：对齐百度作家平台官方分类）
# v1.5.0 修复：不要求 AI 图像模型画文字（它只能"画"字不能"写"字，必然乱码）
# 书名文字改为 Pillow 后期叠加
SCENE_PROMPT_TEMPLATE = """你是一位资深图书封面设计师。请根据以下信息生成一段英文画面描述，用于 AI 文生图。

【作品性向】{gender}（男性向偏热血/历史/都市；女性向偏言情/青春/情感；无性向偏悬疑/现实/杂谈）
【作品类型】{genre}（百度作家平台官方二级分类）
【小说名】{name}
【梗概核心】{synopsis_excerpt}

【输出要求】
1. 输出一段 100-200 词的英文画面描述
2. 描述封面构图、色调、主体元素、氛围
3. 【重要】封面图片上不要包含任何文字、标题、字符或书法：an image with no text, no characters, no calligraphy, no typography
4. 不得包含违规或敏感内容
5. 只输出画面描述本身，不要输出其他解释
"""

# 固定模板降级 Prompt（spec 5.8.3 异常场景 2）
# v1.5.0：移除 with title text 要求（AI 图像模型画中文会乱码）
FALLBACK_PROMPT_TEMPLATE = (
    'Book cover design, {gender} style, {genre} genre, '
    "vertical book cover format, atmospheric lighting, detailed illustration, "
    "no text, no characters, no calligraphy, "
    "no watermark, high quality"
)


class CoverGenerationError(Exception):
    """封面生成失败"""
    pass


def _build_scene_prompt(gender: str, genre: str, name: str, synopsis: str) -> str:
    """构造 LLM 画面描述 Prompt"""
    synopsis_excerpt = (synopsis or "")[:200]
    return SCENE_PROMPT_TEMPLATE.format(
        gender=gender, genre=genre, name=name, synopsis_excerpt=synopsis_excerpt
    )


def _build_fallback_prompt(gender: str, genre: str, name: str) -> str:
    """构造固定模板降级 Prompt"""
    return FALLBACK_PROMPT_TEMPLATE.format(gender=gender, genre=genre, name=name)


def _orchestrate_scene_description(gender: str, genre: str, name: str, synopsis: str) -> tuple:
    """Agnes LLM 编排英文画面描述。

    Returns: (prompt, is_degraded)
    - 成功：(LLM 生成的英文描述, False)
    - 失败：(固定模板 Prompt, True)
    """
    mm = ModelManager()
    prompt_text = _build_scene_prompt(gender, genre, name, synopsis)
    try:
        # spec v1.4.0：改用 role=cover_planner（Agnes LLM）
        result = mm.call_llm(prompt_text, role="cover_planner", temperature=0.7, max_tokens=512)
        result = (result or "").strip()
        if len(result) < 20:
            logger.warning("LLM 画面描述过短，降级到固定模板")
            return _build_fallback_prompt(gender, genre, name), True
        logger.info("Agnes LLM 画面描述生成成功")
        return result, False
    except Exception as e:
        logger.warning(f"Agnes LLM 画面描述生成失败，降级到固定模板: {e}", exc_info=True)
        return _build_fallback_prompt(gender, genre, name), True


def _find_chinese_font() -> str | None:
    """查找系统中可用的中文字体路径。
    按优先级尝试多个常见路径，Windows / Linux / macOS 兼容。
    Returns: 字体文件绝对路径，找不到则返回 None。
    """
    font_candidates = [
        # Windows 常见中文字体
        r"C:\Windows\Fonts\msyh.ttc",        # 微软雅黑
        r"C:\Windows\Fonts\simfang.ttf",     # 仿宋（书封风格）
        r"C:\Windows\Fonts\simkai.ttf",      # 楷体（书封风格）
        r"C:\Windows\Fonts\simhei.ttf",      # 黑体
        r"C:\Windows\Fonts\msyhbd.ttc",      # 微软雅黑粗体
        # Linux 常见中文字体（Docker 常用）
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        # 项目内自定义字体目录
        os.path.join(settings.STATIC_DIR, "fonts", "zh_font.ttf"),
        os.path.join(settings.STATIC_DIR, "fonts", "zh_font.ttc"),
    ]
    for path in font_candidates:
        if os.path.exists(path):
            logger.info(f"使用中文字体: {path}")
            return path
    logger.warning("未找到中文字体，书名将无法叠加到封面")
    return None


def _overlay_book_title(image_path: str, book_name: str) -> str:
    """使用 Pillow 在封面图片上叠加书名文字。

    在图片底部留白区域叠加书名，白字半透明底框，保证可读性。
    如果找不到中文字体则跳过叠加，原图返回。

    Args:
        image_path: 原图绝对路径
        book_name: 书名（中文字符串）

    Returns: 叠加文字后的图片路径（可能与原路径相同）
    """
    font_path = _find_chinese_font()
    if font_path is None:
        logger.warning("无可用中文字体，跳过书名叠加")
        return image_path

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow 未安装，跳过书名叠加")
        return image_path

    img = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    # 字体大小：封面宽度的 1/12 ~ 1/10，最小 28px
    font_size = max(28, min(72, w // 10))
    try:
        # ttc 字体需要指定 index（微软雅黑通常 index=0）
        font = ImageFont.truetype(font_path, font_size, index=0)
    except Exception:
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception as e:
            logger.warning(f"加载字体失败: {e}")
            return image_path

    # 计算文字边界框
    bbox = draw.textbbox((0, 0), book_name, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # 文字区域：底部留白，居中放置
    padding_h = min(80, h // 8)
    text_x = (w - tw) // 2
    text_y = h - th - padding_h

    # 半透明底框，增强文字可读性
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    box_padding = font_size // 3
    overlay_draw.rounded_rectangle(
        [text_x - box_padding, text_y - box_padding,
         text_x + tw + box_padding, text_y + th + box_padding],
        radius=font_size // 6,
        fill=(0, 0, 0, 140),
    )
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # 画文字（白色，加轻微投影增强立体感）
    shadow_offset = max(1, font_size // 24)
    draw.text((text_x + shadow_offset, text_y + shadow_offset), book_name, font=font, fill=(0, 0, 0, 80))
    draw.text((text_x, text_y), book_name, font=font, fill=(255, 255, 255, 255))

    # 保存覆盖原图
    img_rgb = img.convert("RGB")
    img_rgb.save(image_path, "PNG")
    logger.info(f"书名[{book_name}]已叠加到封面: {image_path}")
    return image_path


def _download_and_save(image_url: str, project_id: str) -> str:
    """下载图片到本地，返回本地文件路径"""
    resp = requests.get(image_url, timeout=60)
    resp.raise_for_status()
    os.makedirs(settings.COVERS_DIR, exist_ok=True)
    timestamp = int(time.time())
    filename = f"{project_id}_{timestamp}.png"
    filepath = os.path.join(settings.COVERS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(resp.content)
    logger.info(f"封面图片已保存: {filepath} ({len(resp.content)} bytes)")
    return filepath


def generate_cover(project_id: str, gender: str, genre: str, name: str, synopsis: str) -> dict:
    """生成封面（spec 5.8.1 规则 4，v1.4.0 改造：Agnes 图像 API）。

    流程：
    1. Agnes LLM 编排画面描述（不要求画文字，避免 AI 文字乱码）
    2. Agnes 图像 API 生成纯画面
    3. 下载到本地
    4. Pillow 叠加书名文字（中文由本地字体渲染，清晰正确）
    5. 返回 cover_url

    Args:
        project_id: 项目 ID
        gender: 作品性向（男性向/女性向/无性向）
        genre: 作品类型
        name: 小说名
        synopsis: 故事梗概

    Returns: {"cover_url": "/static/covers/xxx.png", "prompt_used": "...", "model_used": "agnes-image-2.1-flash"}

    Raises: CoverGenerationError 当 Agnes 图像 API 不可达时
    """
    logger.info(f"开始生成封面: project={project_id}, gender={gender}, genre={genre}, name={name}")

    # 步骤1：Agnes LLM 编排画面描述（降级到固定模板）
    prompt, is_degraded = _orchestrate_scene_description(gender, genre, name, synopsis)
    if is_degraded:
        logger.warning("使用固定模板 Prompt 生成封面")

    # 步骤2：调用 Agnes 图像 API（同步返回，无需轮询）
    try:
        image_url = generate_image(prompt, size=IMAGE_SIZE)
    except AgnesImageError as e:
        raise CoverGenerationError(f"Agnes 图像 API 失败: {e}")

    # 步骤3：下载图片到本地
    filepath = _download_and_save(image_url, project_id)

    # 步骤4：Pillow 叠加书名文字（AI 图像模型无法可靠生成中文）
    if name.strip():
        _overlay_book_title(filepath, name.strip())
    else:
        logger.warning("书名为空，跳过书名叠加")

    # 构建封面 URL（基于文件路径）
    filename = os.path.basename(filepath)
    cover_url = f"/static/covers/{filename}"

    return {
        "cover_url": cover_url,
        "prompt_used": prompt,
        "model_used": AGNES_IMAGE_MODEL,
    }
