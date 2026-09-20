import pytest
import json
from unittest.mock import patch, MagicMock


class TestSceneSplitter:
    def setup_method(self):
        from app.services.scene_splitter import SceneSplitter
        self.splitter = SceneSplitter()

    @patch("app.services.scene_splitter.ModelManager")
    def test_split_chapter_success(self, MockModelManager):
        mock_mgr = MagicMock()
        mock_mgr.call_llm.return_value = json.dumps([
            {
                "scene_id": 1,
                "visual_prompt": "A misty mountain landscape at dawn with a lone figure standing on a cliff edge",
                "dialogue": "林婉：你真的要走吗？",
                "narration": "清晨的雾气笼罩着整个山谷",
                "camera_movement": "pan_left",
                "duration_seconds": 8
            },
            {
                "scene_id": 2,
                "visual_prompt": "Close-up of a woman's face with tears in her eyes",
                "dialogue": "",
                "narration": "她知道这一别或许就是永别",
                "camera_movement": "zoom_in",
                "duration_seconds": 6
            },
            {
                "scene_id": 3,
                "visual_prompt": "A man walking away on a mountain path disappearing into fog",
                "dialogue": "顾辰：等我回来。",
                "narration": "",
                "camera_movement": "tracking",
                "duration_seconds": 10
            }
        ])
        MockModelManager.return_value = mock_mgr

        result = self.splitter.split_chapter(
            chapter_content="章节内容...",
            characters={"顾辰": "男主角", "林婉": "女主角"},
            style="中国风水墨",
            platform="douyin"
        )

        assert len(result) >= 3
        assert result[0]["scene_id"] == 1
        assert "visual_prompt" in result[0]

    @patch("app.services.scene_splitter.ModelManager")
    def test_split_chapter_invalid_json_with_robust_parse(self, MockModelManager):
        mock_mgr = MagicMock()
        mock_mgr.call_llm.return_value = '```json\n[{"scene_id": 1, "visual_prompt": "test prompt", "dialogue": "", "narration": "旁白", "camera_movement": "static", "duration_seconds": 8}]\n```'
        MockModelManager.return_value = mock_mgr

        result = self.splitter.split_chapter(
            chapter_content="章节内容...",
            characters={},
            style="写实风格",
            platform="douyin"
        )

        assert len(result) >= 1
        assert result[0]["visual_prompt"] == "test prompt"

    @patch("app.services.scene_splitter.ModelManager")
    def test_split_chapter_fewer_than_3_scenes(self, MockModelManager):
        mock_mgr = MagicMock()
        mock_mgr.call_llm.return_value = json.dumps([
            {"scene_id": 1, "visual_prompt": "scene 1", "dialogue": "", "narration": "n1", "camera_movement": "static", "duration_seconds": 8}
        ])
        MockModelManager.return_value = mock_mgr

        result = self.splitter.split_chapter(
            chapter_content="章节内容...",
            characters={},
            style="中国风水墨",
            platform="douyin"
        )

        assert len(result) >= 3

    @patch("app.services.scene_splitter.ModelManager")
    def test_split_chapter_more_than_8_scenes(self, MockModelManager):
        scenes = [
            {"scene_id": i, "visual_prompt": f"scene {i}", "dialogue": "", "narration": f"n{i}", "camera_movement": "static", "duration_seconds": 5}
            for i in range(1, 12)
        ]
        mock_mgr = MagicMock()
        mock_mgr.call_llm.return_value = json.dumps(scenes)
        MockModelManager.return_value = mock_mgr

        result = self.splitter.split_chapter(
            chapter_content="章节内容...",
            characters={},
            style="中国风水墨",
            platform="douyin"
        )

        assert len(result) <= 8

    @patch("app.services.scene_splitter.ModelManager")
    def test_split_chapter_missing_visual_prompt(self, MockModelManager):
        mock_mgr = MagicMock()
        mock_mgr.call_llm.return_value = json.dumps([
            {"scene_id": 1, "visual_prompt": "", "dialogue": "对话", "narration": "旁白", "camera_movement": "static", "duration_seconds": 8}
        ])
        MockModelManager.return_value = mock_mgr

        result = self.splitter.split_chapter(
            chapter_content="这是一段关于山谷中离别的章节内容，讲述了林婉和顾辰的故事。",
            characters={},
            style="中国风水墨",
            platform="douyin"
        )

        assert len(result) >= 1
        assert len(result[0]["visual_prompt"]) > 0