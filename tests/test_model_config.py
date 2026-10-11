"""Independent text/vision providers; never read real keys or call a network."""
import os
import runpy
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr

ROOT = Path(__file__).resolve().parents[1]


def load_config(env):
    with patch.dict(os.environ, env, clear=True), patch("dotenv.load_dotenv", return_value=False):
        return runpy.run_path(str(ROOT / "config.py"))


def test_defaults_are_deepseek_text_and_qwen_vision():
    cfg = load_config({})
    assert cfg.get("DEEPSEEK_BASE_URL") == "https://api.deepseek.com"
    assert cfg.get("DEEPSEEK_MODEL") == "deepseek-flash"
    assert cfg.get("VISION_BASE_URL") == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert cfg.get("VISION_MODEL") == "qwen3-vl-plus"
    assert cfg.get("VISION_API_KEY") is None


def test_text_and_vision_have_separate_configurations():
    cfg = load_config({"DEEPSEEK_API_KEY": "text-test", "DEEPSEEK_BASE_URL": "https://text.example/v1",
                       "DEEPSEEK_MODEL": "deepseek-flash", "VISION_API_KEY": "vision-test",
                       "VISION_BASE_URL": "https://vision.example/v1", "VISION_MODEL": "custom-vision"})
    assert cfg.get("DEEPSEEK_API_KEY") == "text-test"
    assert cfg.get("VISION_API_KEY") == "vision-test"
    assert cfg.get("VISION_BASE_URL") != cfg.get("DEEPSEEK_BASE_URL")


def test_dashscope_key_is_only_a_vision_alias():
    cfg = load_config({"DEEPSEEK_API_KEY": "text-test", "DASHSCOPE_API_KEY": "dashscope-test"})
    assert cfg.get("VISION_API_KEY") == "dashscope-test"
    assert cfg.get("DEEPSEEK_API_KEY") == "text-test"


def test_text_only_startup_does_not_require_vision_key():
    cfg = load_config({"DEEPSEEK_API_KEY": "text-test", "MEMORY_BACKEND": "memory"})
    cfg["validate"]()


def test_missing_text_key_uses_deepseek_name():
    cfg = load_config({})
    with pytest.raises(EnvironmentError, match="DEEPSEEK_API_KEY"):
        cfg["validate"]()


def test_model_instances_do_not_share_credentials_or_text_options():
    import config
    with patch.multiple(config, DEEPSEEK_API_KEY="text-test", DEEPSEEK_BASE_URL="https://text.example/v1",
                        DEEPSEEK_MODEL="deepseek-flash", VISION_API_KEY="vision-test",
                        VISION_BASE_URL="https://vision.example/v1", VISION_MODEL="qwen3-vl-plus",
                        SILICONFLOW_API_KEY=None, create=True):
        models = runpy.run_path(str(ROOT / "llms.py"))
    assert models["answer_LLM"].model_name == "deepseek-flash"
    assert models["router_LLM"].openai_api_key == SecretStr("text-test")
    assert models["vision_LLM"].openai_api_key == SecretStr("vision-test")
    assert models["vision_LLM"].openai_api_base == "https://vision.example/v1"
    assert models["vision_LLM"].model_name == "qwen3-vl-plus"
    assert models["vision_LLM"].extra_body is None


def test_missing_vision_key_does_not_fall_back_to_text_key():
    import config
    with patch.multiple(config, DEEPSEEK_API_KEY="text-test", DEEPSEEK_BASE_URL="https://api.deepseek.com",
                        DEEPSEEK_MODEL="deepseek-flash", VISION_API_KEY=None,
                        VISION_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1",
                        VISION_MODEL="qwen3-vl-plus", SILICONFLOW_API_KEY=None, create=True):
        models = runpy.run_path(str(ROOT / "llms.py"))
    assert models["vision_LLM"] is None
