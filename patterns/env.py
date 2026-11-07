"""
Unified LLM Environment and Client Configuration for Agentic Design Patterns.

This module provides standardized environment variable loading and model client
initialization for all examples in patterns/ (LangChain, AutoGen, CrewAI).

Supported Environment Variables:
  - LLM_PROVIDER: "ollama" (default) or "openai"
  - LLM_MODEL: Model name (defaults to provider-recommended models, e.g. "deepseek-r1:8b" or "gpt-4o-mini")
  - OLLAMA_HOST: Ollama server endpoint (default: "http://localhost:11434")
  - LLM_BASE_URL: Generic base URL fallback for Ollama/OpenAI
  - OPENAI_API_KEY: OpenAI API key (for openai provider)
  - OPENAI_BASE_URL: Custom OpenAI endpoint or compatible proxy
  - LLM_TEMPERATURE: Optional global default temperature
"""

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import find_dotenv, load_dotenv

# Automatically load .env from current directory or any parent directory
_DOTENV_PATH = find_dotenv(usecwd=True)
if not _DOTENV_PATH:
    # Fallback to searching up from this file's location (repo root)
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


def get_provider(default: str = "ollama") -> str:
    """Get configured LLM provider ('ollama' or 'openai')."""
    return (os.getenv("LLM_PROVIDER") or default).strip().lower()


def get_model(default: Optional[str] = None, provider: Optional[str] = None) -> str:
    """Get model name from environment or fallback default."""
    model = os.getenv("LLM_MODEL")
    if model and model.strip():
        return model.strip()
    if default:
        return default
    prov = (provider or get_provider()).lower()
    if prov == "openai":
        return "gpt-4o-mini"
    return "deepseek-r1:8b"


def get_ollama_host(default: str = "http://localhost:11434") -> str:
    """Get Ollama service endpoint."""
    return (
        os.getenv("OLLAMA_HOST")
        or os.getenv("LLM_BASE_URL")
        or default
    ).strip().rstrip("/")


def get_openai_api_key() -> Optional[str]:
    """Get OpenAI API key if configured."""
    key = os.getenv("OPENAI_API_KEY")
    return key.strip() if key else None


def get_openai_base_url() -> Optional[str]:
    """Get OpenAI Base URL if configured."""
    url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL")
    return url.strip().rstrip("/") if url else None


def get_temperature(default: float = 0.7) -> float:
    """Get model temperature from environment if set."""
    val = os.getenv("LLM_TEMPERATURE")
    if val:
        try:
            return float(val.strip())
        except ValueError:
            pass
    return default


def create_langchain_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    default: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Create a LangChain ChatModel instance according to environment configuration."""
    prov = (provider or get_provider()).lower()

    if prov == "openai":
        from langchain_openai import ChatOpenAI

        name = model_name or get_model(default=default or "gpt-4o-mini", provider="openai")
        params: dict[str, Any] = {"model": name, **kwargs}
        if temperature is not None:
            params["temperature"] = temperature
        api_key = get_openai_api_key()
        if api_key:
            params["api_key"] = api_key
        base_url = get_openai_base_url()
        if base_url:
            params["base_url"] = base_url
        return ChatOpenAI(**params)

    if prov == "ollama":
        from langchain_ollama import ChatOllama

        name = model_name or get_model(default=default or "deepseek-r1:14b", provider="ollama")
        host = get_ollama_host()
        params = {"model": name, "base_url": host, **kwargs}
        if temperature is not None:
            params["temperature"] = temperature
        return ChatOllama(**params)

    raise ValueError(f"Unsupported provider: {prov}. Use 'openai' or 'ollama'.")


def create_autogen_client(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    default: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Create an AutoGen model client according to environment configuration."""
    prov = (provider or get_provider()).lower()

    if prov == "openai":
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        name = model_name or get_model(default=default or "gpt-4o-mini", provider="openai")
        params: dict[str, Any] = {"model": name, **kwargs}
        if temperature is not None:
            params["temperature"] = temperature
        api_key = get_openai_api_key()
        if api_key:
            params["api_key"] = api_key
        base_url = get_openai_base_url()
        if base_url:
            params["base_url"] = base_url
        return OpenAIChatCompletionClient(**params)

    if prov == "ollama":
        from autogen_ext.models.ollama import OllamaChatCompletionClient

        name = model_name or get_model(default=default or "qwen3:8b", provider="ollama")
        host = get_ollama_host()
        params = {"model": name, "host": host, **kwargs}
        if temperature is not None:
            params["temperature"] = temperature
        return OllamaChatCompletionClient(**params)

    raise ValueError(f"Unsupported provider: {prov}. Use 'openai' or 'ollama'.")


def create_crewai_llm(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    default: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Create a CrewAI LLM instance according to environment configuration."""
    from crewai import LLM

    prov = (provider or get_provider()).lower()

    if prov == "openai":
        name = model_name or get_model(default=default or "gpt-4o-mini", provider="openai")
        params: dict[str, Any] = {"model": name, **kwargs}
        if temperature is not None:
            params["temperature"] = temperature
        api_key = get_openai_api_key()
        if api_key:
            params["api_key"] = api_key
        base_url = get_openai_base_url()
        if base_url:
            params["base_url"] = base_url
        return LLM(**params)

    if prov == "ollama":
        name = model_name or get_model(default=default or "deepseek-r1:14b", provider="ollama")
        host = get_ollama_host()
        params = {"model": f"ollama/{name}", "base_url": host, **kwargs}
        if temperature is not None:
            params["temperature"] = temperature
        return LLM(**params)

    raise ValueError(f"Unsupported provider: {prov}. Use 'openai' or 'ollama'.")
