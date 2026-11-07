import os
import unittest
from unittest.mock import patch

from patterns.env import (
    get_provider,
    get_model,
    get_ollama_host,
    get_openai_api_key,
    get_openai_base_url,
    get_temperature,
    load_patterns_env,
)


class TestPatternsEnv(unittest.TestCase):
    def test_default_provider(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_provider(), "ollama")

    def test_custom_provider(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            self.assertEqual(get_provider(), "openai")

    def test_get_model_from_env(self):
        with patch.dict(os.environ, {"LLM_MODEL": "custom-model:3b"}):
            self.assertEqual(get_model(), "custom-model:3b")

    def test_get_model_fallback_by_provider(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_model(provider="ollama"), "deepseek-r1:8b")
            self.assertEqual(get_model(provider="openai"), "gpt-4o-mini")

    def test_get_model_explicit_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_model(default="qwen3:8b"), "qwen3:8b")

    def test_get_ollama_host(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_ollama_host(), "http://localhost:11434")

        with patch.dict(os.environ, {"OLLAMA_HOST": "http://192.168.1.50:11434/"}):
            self.assertEqual(get_ollama_host(), "http://192.168.1.50:11434")

        with patch.dict(os.environ, {"LLM_BASE_URL": "http://gpu-server:11434"}):
            self.assertEqual(get_ollama_host(), "http://gpu-server:11434")

    def test_get_openai_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(get_openai_api_key())
            self.assertIsNone(get_openai_base_url())

        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-test-key",
            "OPENAI_BASE_URL": "https://api.openai.com/v1/",
        }):
            self.assertEqual(get_openai_api_key(), "sk-test-key")
            self.assertEqual(get_openai_base_url(), "https://api.openai.com/v1")

    def test_get_temperature(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_temperature(0.5), 0.5)

        with patch.dict(os.environ, {"LLM_TEMPERATURE": "0.2"}):
            self.assertEqual(get_temperature(), 0.2)


if __name__ == "__main__":
    unittest.main()
