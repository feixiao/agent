"""
Unified LLM Environment and Client Configuration for Agentic Design Patterns.

All pattern examples connect through the universal OpenAI-compatible API protocol.
Compatible with LM Studio, Ollama (/v1), vLLM, DeepSeek, OpenAI, etc.

You only need to configure two core settings in .env:
  - LLM_BASE_URL: Model server endpoint (e.g. http://localhost:1234/v1 for LM Studio, http://localhost:11434/v1 for Ollama)
  - LLM_MODEL: Model identifier (e.g. qwen3.8-27b-splash)

Optional settings:
  - LLM_API_KEY: API authentication key (defaults to 'not-needed' for local servers)
  - LLM_TEMPERATURE: Sampling temperature (default: 0.7)
"""

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import find_dotenv, load_dotenv

# Automatically load .env from current working directory or upward
_DOTENV_PATH = find_dotenv(usecwd=True)
if not _DOTENV_PATH:
    repo_root = Path(__file__).resolve().parent.parent
    candidate = repo_root / ".env"
    if candidate.exists():
        _DOTENV_PATH = str(candidate)

if _DOTENV_PATH:
    load_dotenv(_DOTENV_PATH, override=False)


def load_patterns_env() -> bool:
    """Explicitly trigger environment variable reloading from .env."""
    dotenv_path = find_dotenv(usecwd=True)
    if not dotenv_path:
        repo_root = Path(__file__).resolve().parent.parent
        candidate = repo_root / ".env"
        if candidate.exists():
            dotenv_path = str(candidate)
    if dotenv_path:
        return load_dotenv(dotenv_path, override=True)
    return False


def get_base_url(default: str = "http://localhost:1234/v1") -> str:
    """Get normalized OpenAI-compatible server endpoint."""
    url = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("OLLAMA_HOST")
        or default
    ).strip().rstrip("/")

    # Ensure /v1 endpoint suffix for standard OpenAI compatibility
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


def get_model(default: Optional[str] = None, provider: Optional[str] = None) -> str:
    """Get model name from environment or fallback default."""
    model = os.getenv("LLM_MODEL")
    if model and model.strip():
        return model.strip()
    return default or "qwen3.8-27b-splash"


def get_api_key(default: str = "not-needed") -> str:
    """Get API Key (defaults to 'not-needed' for local LM Studio / Ollama servers)."""
    return (
        os.getenv("LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or default
    ).strip()


def get_temperature(default: float = 0.7) -> float:
    """Get sampling temperature from environment if configured."""
    val = os.getenv("LLM_TEMPERATURE")
    if val:
        try:
            return float(val.strip())
        except ValueError:
            pass
    return default


# Backward compatibility aliases
def get_provider(default: str = "openai") -> str:
    return (os.getenv("LLM_PROVIDER") or default).strip().lower()


def get_ollama_host(default: str = "http://localhost:11434") -> str:
    return os.getenv("OLLAMA_HOST") or get_base_url(default)


def get_openai_api_key() -> Optional[str]:
    return get_api_key()


def get_openai_base_url() -> Optional[str]:
    return get_base_url()


def create_langchain_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    default: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Create a LangChain ChatModel instance connecting to an OpenAI-compatible endpoint."""
    # Check if user explicitly requested legacy native Ollama client without base_url
    prov = (provider or os.getenv("LLM_PROVIDER") or "").lower()
    if prov == "ollama" and not os.getenv("LLM_BASE_URL"):
        from langchain_ollama import ChatOllama

        name = model_name or get_model(default=default or "qwen3.8-27b-splash")
        host = os.getenv("OLLAMA_HOST") or "http://localhost:11434"
        params = {"model": name, "base_url": host, **kwargs}
        if temperature is not None:
            params["temperature"] = temperature
        return ChatOllama(**params)

    # Standard universal path: ChatOpenAI against any OpenAI-compatible server (LM Studio, Ollama /v1, vLLM, OpenAI)
    from langchain_openai import ChatOpenAI

    name = model_name or get_model(default=default or "qwen3.8-27b-splash")
    target_base_url = base_url or get_base_url()
    target_api_key = api_key or get_api_key()

    params: dict[str, Any] = {
        "model": name,
        "base_url": target_base_url,
        "api_key": target_api_key,
        **kwargs,
    }
    if temperature is not None:
        params["temperature"] = temperature

    return ChatOpenAI(**params)


def create_autogen_client(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    default: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Create an AutoGen model client connecting to an OpenAI-compatible endpoint."""
    prov = (provider or os.getenv("LLM_PROVIDER") or "").lower()
    if prov == "ollama" and not os.getenv("LLM_BASE_URL"):
        from autogen_ext.models.ollama import OllamaChatCompletionClient

        name = model_name or get_model(default=default or "qwen3.8-27b-splash")
        host = os.getenv("OLLAMA_HOST") or "http://localhost:11434"
        params = {"model": name, "host": host, **kwargs}
        if temperature is not None:
            params["temperature"] = temperature
        return OllamaChatCompletionClient(**params)

    # Standard universal path: OpenAIChatCompletionClient with auto-attached ModelInfo
    from autogen_core.models import ModelInfo
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    name = model_name or get_model(default=default or "qwen3.8-27b-splash")
    target_base_url = base_url or get_base_url()
    target_api_key = api_key or get_api_key()

    default_model_info: ModelInfo = {
        "vision": False,
        "function_calling": True,
        "json_output": True,
        "structured_output": True,
        "family": "unknown",
    }
    model_info = kwargs.pop("model_info", default_model_info)

    params: dict[str, Any] = {
        "model": name,
        "base_url": target_base_url,
        "api_key": target_api_key,
        "model_info": model_info,
        **kwargs,
    }
    if temperature is not None:
        params["temperature"] = temperature

    return OpenAIChatCompletionClient(**params)


def create_crewai_llm(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    default: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Create a CrewAI LLM instance connecting to an OpenAI-compatible endpoint."""
    from crewai import LLM

    name = model_name or get_model(default=default or "qwen3.8-27b-splash")
    target_base_url = base_url or get_base_url()
    target_api_key = api_key or get_api_key()

    # Prefix with openai/ to ensure LiteLLM routes via OpenAI-compatible completions API
    model_identifier = name if name.startswith("openai/") else f"openai/{name}"

    params: dict[str, Any] = {
        "model": model_identifier,
        "base_url": target_base_url,
        "api_key": target_api_key,
        **kwargs,
    }
    if temperature is not None:
        params["temperature"] = temperature

    return LLM(**params)
