import os
import unittest
from unittest.mock import patch

from patterns.env import (
    create_autogen_client,
    create_crewai_llm,
    create_langchain_model,
    get_api_key,
    get_base_url,
    get_model,
    get_temperature,
)


class TestPatternsEnv(unittest.TestCase):
    def test_default_base_url(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_base_url(), "http://localhost:1234/v1")

    def test_custom_base_url_auto_v1_suffix(self):
        # 自动补全 /v1 后缀以兼容各类本地推理服务 (LM Studio, Ollama 等)
        with patch.dict(os.environ, {"LLM_BASE_URL": "http://localhost:11434"}):
            self.assertEqual(get_base_url(), "http://localhost:11434/v1")

        with patch.dict(os.environ, {"LLM_BASE_URL": "http://192.168.1.100:1234/v1/"}):
            self.assertEqual(get_base_url(), "http://192.168.1.100:1234/v1")

    def test_get_model(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_model(), "qwen3.8-27b-splash")

        with patch.dict(os.environ, {"LLM_MODEL": "my-local-model"}):
            self.assertEqual(get_model(), "my-local-model")

    def test_get_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_api_key(), "not-needed")

        with patch.dict(os.environ, {"LLM_API_KEY": "custom-key"}):
            self.assertEqual(get_api_key(), "custom-key")

    def test_get_temperature(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_temperature(0.5), 0.5)

        with patch.dict(os.environ, {"LLM_TEMPERATURE": "0.3"}):
            self.assertEqual(get_temperature(), 0.3)

    def test_factories_creation(self):
        with patch.dict(os.environ, {
            "LLM_BASE_URL": "http://localhost:1234/v1",
            "LLM_MODEL": "qwen3.8-27b-splash",
            "LLM_API_KEY": "test-key",
        }):
            lc_model = create_langchain_model()
            self.assertEqual(getattr(lc_model, "model_name", None), "qwen3.8-27b-splash")

            ag_client = create_autogen_client()
            self.assertEqual(type(ag_client).__name__, "OpenAIChatCompletionClient")

            cr_llm = create_crewai_llm()
            self.assertEqual(cr_llm.model, "qwen3.8-27b-splash")


if __name__ == "__main__":
    unittest.main()
