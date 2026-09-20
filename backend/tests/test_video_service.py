import pytest
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
import httpx


class TestVideoService:
    def setup_method(self):
        from app.services.video_service import VideoService
        self.service = VideoService()

    def test_validate_num_frames_valid(self):
        assert self.service.validate_num_frames(121) == 121
        assert self.service.validate_num_frames(9) == 9
        assert self.service.validate_num_frames(441) == 441

    def test_validate_num_frames_invalid_adjusts_to_8n_plus_1(self):
        result = self.service.validate_num_frames(100)
        assert result <= 441
        assert (result - 1) % 8 == 0

    def test_validate_num_frames_exceeds_max(self):
        result = self.service.validate_num_frames(500)
        assert result <= 441
        assert (result - 1) % 8 == 0

    def test_platform_presets(self):
        from app.services.video_service import PLATFORM_PRESETS
        assert PLATFORM_PRESETS["douyin"]["width"] == 768
        assert PLATFORM_PRESETS["douyin"]["height"] == 1344
        assert PLATFORM_PRESETS["youku"]["width"] == 1152
        assert PLATFORM_PRESETS["youku"]["height"] == 768

    @patch("httpx.post")
    def test_create_video_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "task_123",
            "video_id": "vid_456",
            "status": "queued"
        }
        mock_post.return_value = mock_response

        result = self.service.create_video("A misty mountain landscape at dawn")
        assert result["task_id"] == "task_123"
        assert result["video_id"] == "vid_456"
        assert result["status"] == "queued"

    @patch("httpx.post")
    def test_create_video_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        with pytest.raises(Exception):
            self.service.create_video("test prompt")

    @patch("httpx.get")
    def test_poll_video_status_completed(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "completed",
            "metadata": {"url": "https://cdn.agnes.ai/video.mp4"}
        }
        mock_get.return_value = mock_response

        result = self.service.poll_video_status("vid_456", max_wait=10, interval=1)
        assert result["status"] == "completed"
        assert result["url"] == "https://cdn.agnes.ai/video.mp4"

    @patch("httpx.get")
    def test_poll_video_status_timeout(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "processing"}
        mock_get.return_value = mock_response

        with pytest.raises(TimeoutError):
            self.service.poll_video_status("vid_456", max_wait=2, interval=1)

    @patch("httpx.get")
    def test_download_video_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake_video_bytes"
        mock_get.return_value = mock_response

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test.mp4")
            result = self.service.download_video("https://cdn.agnes.ai/video.mp4", save_path)
            assert os.path.exists(result)
            with open(result, "rb") as f:
                assert f.read() == b"fake_video_bytes"