"""TDD 测试：封面生成服务（spec 5.8 / design 1.3.8，v1.4.0 改造：Agnes 图像 API）"""
import os
import pytest
from unittest.mock import patch, MagicMock

from app.services import cover_service
from app.services.cover_service import (
    CoverGenerationError,
    generate_cover,
    _orchestrate_scene_description,
    _build_fallback_prompt,
    _download_and_save,
    _overlay_book_title,
)


class TestOrchestrateSceneDescription:
    """LLM 编排画面描述测试"""

    def test_llm_success(self):
        """LLM 成功生成英文画面描述"""
        with patch.object(cover_service, "ModelManager") as MockMM:
            mm = MockMM.return_value
            mm.call_llm.return_value = (
                "A dark, atmospheric book cover with a silhouette standing under a dim streetlight, "
                "rain-soaked alley, moody blue and gray tones, mystery and suspense atmosphere."
            )
            prompt, degraded = _orchestrate_scene_description(
                "无性向", "悬疑", "夜色微凉", "一个雨夜的故事..."
            )
            assert not degraded
            assert "streetlight" in prompt or "silhouette" in prompt
            mm.call_llm.assert_called_once()

    def test_llm_failure_fallback(self):
        """LLM 失败时降级到固定模板（spec 5.8.3 异常场景 2）"""
        with patch.object(cover_service, "ModelManager") as MockMM:
            mm = MockMM.return_value
            mm.call_llm.side_effect = Exception("LLM 不可用")
            prompt, degraded = _orchestrate_scene_description(
                "男性向", "玄幻", "修仙路", "少年修仙..."
            )
            assert degraded
            assert "男性向" in prompt
            assert "玄幻" in prompt


    def test_llm_too_short_fallback(self):
        """LLM 返回过短时降级"""
        with patch.object(cover_service, "ModelManager") as MockMM:
            mm = MockMM.return_value
            mm.call_llm.return_value = "短"
            prompt, degraded = _orchestrate_scene_description(
                "女性向", "爱情", "心动", "爱情故事..."
            )
            assert degraded
            assert "女性向" in prompt


class TestAgnesImageClient:
    """Agnes 图像 API 调用测试"""

    def test_generate_image_success(self):
        """Agnes 图像 API 成功返回图片 URL"""
        from app.services.agnes_image_client import generate_image, AgnesImageError
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"url": "https://platform-outputs.agnes-ai.space/img123.png"}]
        }
        with patch("app.services.agnes_image_client.requests.post", return_value=mock_resp), \
             patch.dict(os.environ, {"AGNES_KEY": "fake-key"}):
            url = generate_image("test prompt", size="768x1024")
            assert url == "https://platform-outputs.agnes-ai.space/img123.png"

    def test_generate_image_no_api_key(self):
        """AGNES_KEY 未设置时抛出 AgnesImageError"""
        from app.services.agnes_image_client import generate_image, AgnesImageError
        with patch.dict(os.environ, {"AGNES_KEY": ""}, clear=False):
            with pytest.raises(AgnesImageError, match="AGNES_KEY"):
                generate_image("test prompt")

    def test_generate_image_api_error(self):
        """Agnes 图像 API 返回非200时抛出 AgnesImageError"""
        from app.services.agnes_image_client import generate_image, AgnesImageError
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        with patch("app.services.agnes_image_client.requests.post", return_value=mock_resp), \
             patch.dict(os.environ, {"AGNES_KEY": "fake-key"}):
            with pytest.raises(AgnesImageError, match="403"):
                generate_image("test prompt")

    def test_generate_image_empty_data(self):
        """Agnes 图像 API 返回空 data 时抛出 AgnesImageError"""
        from app.services.agnes_image_client import generate_image, AgnesImageError
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": []}
        with patch("app.services.agnes_image_client.requests.post", return_value=mock_resp), \
             patch.dict(os.environ, {"AGNES_KEY": "fake-key"}):
            with pytest.raises(AgnesImageError, match="空 data"):
                generate_image("test prompt")


class TestDownloadAndSave:
    """图片下载保存测试"""

    def test_download_and_save(self, tmp_path):
        """下载图片并保存到本地"""
        mock_resp = MagicMock()
        mock_resp.content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_resp.raise_for_status = MagicMock()
        with patch.object(cover_service.requests, "get", return_value=mock_resp), \
             patch.object(cover_service.settings, "COVERS_DIR", str(tmp_path)):
            filepath = _download_and_save(
                "https://platform-outputs.agnes-ai.space/image.png", "proj-123"
            )
            assert "proj-123_" in filepath
            assert filepath.endswith(".png")
            assert os.path.exists(filepath)
            assert os.path.getsize(filepath) > 0


class TestOverlayBookTitle:
    """书名叠加测试"""

    def test_overlay_with_font(self, tmp_path):
        """有中文字体时叠加书名"""
        test_img_path = str(tmp_path / "test_cover.png")
        from PIL import Image
        img = Image.new("RGB", (768, 1024), (100, 100, 150))
        img.save(test_img_path, "PNG")

        with patch.object(cover_service, "_find_chinese_font", return_value=r"C:\Windows\Fonts\msyh.ttc"):
            if os.path.exists(r"C:\Windows\Fonts\msyh.ttc"):
                result = _overlay_book_title(test_img_path, "夜色微凉")
                assert result == test_img_path
                assert os.path.exists(result)
            else:
                result = _overlay_book_title(test_img_path, "夜色微凉")
                assert result == test_img_path

    def test_overlay_no_font(self, tmp_path):
        """无中文字体时跳过叠加"""
        test_img_path = str(tmp_path / "test_cover2.png")
        from PIL import Image
        img = Image.new("RGB", (768, 1024), (100, 100, 150))
        img.save(test_img_path, "PNG")

        with patch.object(cover_service, "_find_chinese_font", return_value=None):
            result = _overlay_book_title(test_img_path, "夜色微凉")
            assert result == test_img_path


class TestGenerateCover:
    """generate_cover 集成测试（全 mock）"""

    def test_full_success(self, tmp_path):
        """完整生成流程成功"""
        mock_img_resp = MagicMock()
        mock_img_resp.content = b"\x89PNG" + b"\x00" * 50
        mock_img_resp.raise_for_status = MagicMock()

        with patch.object(cover_service, "ModelManager") as MockMM, \
             patch.object(cover_service, "generate_image", return_value="https://platform-outputs.agnes-ai.space/x.png") as mock_gen_img, \
             patch.object(cover_service.requests, "get", return_value=mock_img_resp), \
             patch.object(cover_service.settings, "COVERS_DIR", str(tmp_path)), \
             patch.object(cover_service, "_overlay_book_title", return_value="mocked_path"):
            mm = MockMM.return_value
            mm.call_llm.return_value = "A mystery book cover with dark tones and a silhouette under streetlight."

            result = generate_cover("proj-1", "无性向", "悬疑", "夜色微凉", "雨夜故事")
            assert result["cover_url"].startswith("/static/covers/proj-1_")
            assert result["model_used"] == "agnes-image-2.1-flash"
            assert "streetlight" in result["prompt_used"]
            mock_gen_img.assert_called_once()

    def test_agnes_image_error_raises(self):
        """Agnes 图像 API 失败时抛出 CoverGenerationError"""
        from app.services.agnes_image_client import AgnesImageError
        with patch.object(cover_service, "ModelManager") as MockMM, \
             patch.object(cover_service, "generate_image", side_effect=AgnesImageError("API 不可达")):
            mm = MockMM.return_value
            mm.call_llm.return_value = "A book cover design."
            with pytest.raises(CoverGenerationError, match="Agnes 图像 API 失败"):
                generate_cover("proj-1", "无性向", "悬疑", "夜色微凉", "雨夜故事")

    def test_degraded_prompt_used(self, tmp_path):
        """LLM 失败时使用降级 Prompt 也能生成封面"""
        mock_img_resp = MagicMock()
        mock_img_resp.content = b"\x89PNG" + b"\x00" * 50
        mock_img_resp.raise_for_status = MagicMock()

        with patch.object(cover_service, "ModelManager") as MockMM, \
             patch.object(cover_service, "generate_image", return_value="https://platform-outputs.agnes-ai.space/x.png"), \
             patch.object(cover_service.requests, "get", return_value=mock_img_resp), \
             patch.object(cover_service.settings, "COVERS_DIR", str(tmp_path)), \
             patch.object(cover_service, "_overlay_book_title", return_value="mocked_path"):
            mm = MockMM.return_value
            mm.call_llm.side_effect = Exception("LLM 不可用")

            result = generate_cover("proj-2", "男性向", "玄幻", "修仙路", "少年修仙")
            assert result["cover_url"].startswith("/static/covers/proj-2_")
            assert "男性向" in result["prompt_used"]
            assert "玄幻" in result["prompt_used"]
