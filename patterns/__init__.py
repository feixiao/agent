"""
Patterns module - Agentic Design Patterns implementations.
"""

from .env import (
    create_autogen_client,
    create_crewai_llm,
    create_langchain_model,
    get_model,
    get_ollama_host,
    get_openai_api_key,
    get_openai_base_url,
    get_provider,
    get_temperature,
    load_patterns_env,
)

__all__ = [
    "load_patterns_env",
    "get_provider",
    "get_model",
    "get_ollama_host",
    "get_openai_api_key",
    "get_openai_base_url",
    "get_temperature",
    "create_langchain_model",
    "create_autogen_client",
    "create_crewai_llm",
]
