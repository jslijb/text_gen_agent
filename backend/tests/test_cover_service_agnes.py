"""封面服务 TDD 测试（spec v1.4.0：Agnes 图像 API 改造）

测试覆盖：
1. Agnes 图像 API 调用成功（mock generate_image）
2. Agnes LLM 画面描述编排成功
3. LLM 失败时降级到固定模板 Prompt
4. Agnes 图像 API 失败时抛出 CoverGenerationError
5. 图片下载保存到本地
6. Project 模型 gender+genre 分层校验
"""
import os
import sys
import json
import shutil
import tempfile
from unittest.mock import patch, MagicMock

import pytest

# 确保能导入 backend 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ==================== Task 13.1: Project 模型 gender+genre 分层 ====================

class TestProjectGenderGenre:
    """spec v1.4.0：Project 模型 gender 字段 + 分类分层"""

    def test_valid_genders(self):
        from app.models.project import Project
        assert Project.VALID_GENDERS == ["男性向", "女性向", "无性向"]

    def test_genres_for_male(self):
        from app.models.project import Project
        assert "都市情感" in Project.get_genres_for_gender("男性向")
        assert "历史故事" in Project.get_genres_for_gender("男性向")
        assert "现代言情" not in Project.get_genres_for_gender("男性向")

    def test_genres_for_female(self):
        from app.models.project import Project
        genres = Project.get_genres_for_gender("女性向")
        assert "现代言情" in genres
        assert "古代言情" in genres
        assert "青春校园" in genres
        assert "婚姻家庭" in genres

    def test_genres_for_neutral(self):
        from app.models.project import Project
        genres = Project.get_genres_for_gender("无性向")
        assert "恐怖推理" in genres
        assert "乡村故事" in genres
        assert "真实故事" in genres
        assert "见闻杂谈" in genres
        assert "复仇爽文" in genres
        assert "特殊职业" in genres

    def test_is_valid_pair(self):
        from app.models.project import Project
        assert Project.is_valid_gender_genre_pair("无性向", "恐怖推理") is True
        assert Project.is_valid_gender_genre_pair("男性向", "都市情感") is True
        assert Project.is_valid_gender_genre_pair("女性向", "现代言情") is True

    def test_invalid_pair(self):
        from app.models.project import Project
        # 无性向下不能选男性向的类型
        assert Project.is_valid_gender_genre_pair("无性向", "都市情感") is False
        # 男性向下不能选女性向的类型
        assert Project.is_valid_gender_genre_pair("男性向", "现代言情") is False
        # 女性向下不能选无性向的类型
        assert Project.is_valid_gender_genre_pair("女性向", "恐怖推理") is False

    def test_genre_migration_map(self):
        """旧 genre → 新 gender+genre 映射"""
        from app.models.project import Project
        # 悬疑推理 → 无性向/恐怖推理
        assert Project.GENRE_MIGRATION_MAP["悬疑推理"] == ("无性向", "恐怖推理")


# ==================== Task 13.3: cover_service Agnes 改造 ====================

class TestCoverServiceAgnes:
    """spec v1.4.0：cover_service 改用 Agnes 图像 API"""

    def test_agnes_image_api_success(self):
        """测试 Agnes 图像 API 调用成功"""
        from app.services import cover_service
        with patch("app.services.cover_service.generate_image") as mock_gen, \
             patch("app.services.cover_service._orchestrate_scene_description") as mock_orch, \
             patch("app.services.cover_service._download_and_save") as mock_dl, \
             patch("app.services.cover_service._overlay_book_title") as mock_overlay:
            mock_orch.return_value = ("a dark alley at night", False)
            mock_gen.return_value = "https://platform-outputs.agnes-ai.space/test.png"
            mock_dl.return_value = "D:/static/covers/test_123.png"
            mock_overlay.return_value = "D:/static/covers/test_123.png"

            result = cover_service.generate_cover("proj1", "无性向", "恐怖推理", "夜色微凉", "故事梗概")

            assert result["cover_url"] == "/static/covers/test_123.png"
            assert result["model_used"] == "agnes-image-2.1-flash"
            mock_gen.assert_called_once_with("a dark alley at night", size="768x1024")

    def test_llm_orchestration_success(self):
        """测试 Agnes LLM 画面描述编排成功"""
        from app.services import cover_service
        with patch("app.services.cover_service.ModelManager") as MockMM:
            mock_mgr = MockMM.return_value
            mock_mgr.call_llm.return_value = "A misty alley at midnight with neon signs flickering"

            prompt, is_degraded = cover_service._orchestrate_scene_description(
                "无性向", "恐怖推理", "夜色微凉", "一个悬疑故事..."
            )
            assert is_degraded is False
            assert "misty alley" in prompt
            # 确认调用了 cover_planner 角色
            mock_mgr.call_llm.assert_called_once()
            args, kwargs = mock_mgr.call_llm.call_args
            assert kwargs.get("role") == "cover_planner"

    def test_llm_failure_fallback_to_template(self):
        """测试 LLM 失败时降级到固定模板"""
        from app.services import cover_service
        with patch("app.services.cover_service.ModelManager") as MockMM:
            mock_mgr = MockMM.return_value
            mock_mgr.call_llm.side_effect = Exception("LLM 不可用")

            prompt, is_degraded = cover_service._orchestrate_scene_description(
                "无性向", "恐怖推理", "夜色微凉", "一个悬疑故事..."
            )
            assert is_degraded is True
            assert "无性向" in prompt
            assert "恐怖推理" in prompt

    def test_llm_short_result_fallback(self):
        """测试 LLM 返回过短时降级"""
        from app.services import cover_service
        with patch("app.services.cover_service.ModelManager") as MockMM:
            mock_mgr = MockMM.return_value
            mock_mgr.call_llm.return_value = "short"  # 少于 20 字符

            prompt, is_degraded = cover_service._orchestrate_scene_description(
                "无性向", "恐怖推理", "夜色微凉", "故事"
            )
            assert is_degraded is True

    def test_agnes_image_api_failure_raises_error(self):
        """测试 Agnes 图像 API 失败时抛出 CoverGenerationError"""
        from app.services import cover_service
        from app.services.agnes_image_client import AgnesImageError
        with patch("app.services.cover_service.generate_image") as mock_gen, \
             patch("app.services.cover_service._orchestrate_scene_description") as mock_orch:
            mock_orch.return_value = ("prompt", False)
            mock_gen.side_effect = AgnesImageError("API 500")

            with pytest.raises(cover_service.CoverGenerationError):
                cover_service.generate_cover("proj1", "无性向", "恐怖推理", "夜色微凉", "梗概")

    def test_download_and_save(self):
        """测试图片下载保存到本地"""
        from app.services import cover_service
        with patch("app.services.cover_service.requests") as mock_req, \
             patch("app.services.cover_service.settings") as mock_settings:
            tmpdir = tempfile.mkdtemp()
            try:
                mock_settings.COVERS_DIR = tmpdir
                mock_resp = MagicMock()
                mock_resp.content = b"\x89PNG fake image bytes"
                mock_resp.raise_for_status.return_value = None
                mock_req.get.return_value = mock_resp

                filepath = cover_service._download_and_save("https://example.com/img.png", "proj123")
                assert "proj123_" in filepath
                assert filepath.endswith(".png")
                files = os.listdir(tmpdir)
                assert len(files) == 1
                assert files[0].startswith("proj123_")
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)


class TestAgnesImageClient:
    """spec v1.4.0：agnes_image_client 单元测试"""

    def test_generate_image_success(self):
        from app.services.agnes_image_client import generate_image
        with patch("app.services.agnes_image_client.requests") as mock_req, \
             patch.dict(os.environ, {"AGNES_KEY": "test_key_123"}):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "data": [{"url": "https://platform-outputs.agnes-ai.space/test.png"}]
            }
            mock_req.post.return_value = mock_resp

            url = generate_image("a dark alley", size="768x1024")
            assert url == "https://platform-outputs.agnes-ai.space/test.png"

    def test_generate_image_no_key(self):
        from app.services.agnes_image_client import generate_image, AgnesImageError
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AgnesImageError, match="AGNES_KEY"):
                generate_image("test prompt")

    def test_generate_image_api_error(self):
        from app.services.agnes_image_client import generate_image, AgnesImageError
        with patch("app.services.agnes_image_client.requests") as mock_req, \
             patch.dict(os.environ, {"AGNES_KEY": "test_key"}):
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.text = "Internal Server Error"
            mock_req.post.return_value = mock_resp

            with pytest.raises(AgnesImageError, match="500"):
                generate_image("test prompt")

    def test_generate_image_empty_data(self):
        from app.services.agnes_image_client import generate_image, AgnesImageError
        with patch("app.services.agnes_image_client.requests") as mock_req, \
             patch.dict(os.environ, {"AGNES_KEY": "test_key"}):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": []}
            mock_req.post.return_value = mock_resp

            with pytest.raises(AgnesImageError, match="空 data"):
                generate_image("test prompt")
