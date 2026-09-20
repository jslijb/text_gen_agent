import pytest
import os
from unittest.mock import patch, MagicMock
from app.services.model_manager import ModelManager, ModelConfig


class TestModelConfig:
    def test_model_config_creation(self):
        config = ModelConfig(
            name="test-model",
            base_url="https://api.test.com/v1",
            api_key_env="TEST_API_KEY",
            quota=1000000,
            priority=1,
            role="writer",
        )
        assert config.name == "test-model"
        assert config.priority == 1
        assert config.role == "writer"
        assert config.status == "available"

    def test_model_config_to_dict(self):
        config = ModelConfig(
            name="test-model",
            base_url="https://api.test.com/v1",
            api_key_env="TEST_API_KEY",
            quota=1000000,
            priority=1,
        )
        d = config.to_dict()
        assert d["name"] == "test-model"
        assert d["status"] == "available"
        assert d["quota"] == 1000000


class TestModelManager:
    def setup_method(self):
        ModelManager._instance = None

    def test_singleton(self):
        with patch.object(ModelManager, '_load_config'):
            m1 = ModelManager()
            m2 = ModelManager()
            assert m1 is m2

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY1": "test-key"})
    def test_get_model_for_role(self):
        with patch.object(ModelManager, '_load_config') as mock_load:
            mgr = ModelManager()
            mgr._models = [
                ModelConfig("model-a", "https://api.test.com/v1", "DASHSCOPE_API_KEY1", 1000000, 1, "planner"),
                ModelConfig("model-b", "https://api.test.com/v1", "DASHSCOPE_API_KEY1", 1000000, 2, "writer"),
            ]
            model = mgr.get_model_for_role("planner")
            assert model is not None
            assert model.name == "model-a"

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY1": "test-key"})
    def test_switch_on_403(self):
        with patch.object(ModelManager, '_load_config'):
            mgr = ModelManager()
            mgr._models = [
                ModelConfig("model-a", "https://api.test.com/v1", "DASHSCOPE_API_KEY1", 1000000, 1, "writer"),
                ModelConfig("model-b", "https://api.test.com/v1", "DASHSCOPE_API_KEY1", 1000000, 2, "writer"),
            ]
            mgr._switch_to_next(mgr._models[0])
            assert mgr._models[0].status == "exhausted"

    @patch.dict(os.environ, {"DASHSCOPE_API_KEY1": "test-key"})
    def test_all_models_exhausted(self):
        with patch.object(ModelManager, '_load_config'):
            mgr = ModelManager()
            mgr._models = [
                ModelConfig("model-a", "https://api.test.com/v1", "DASHSCOPE_API_KEY1", 1000000, 1),
            ]
            mgr._models[0].status = "exhausted"
            model = mgr._get_current_model()
            assert model is None