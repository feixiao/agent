"""Shared packaging and plumbing for the ai-agent-book companion experiments.

This package exists so the repo can declare its dependencies once (see the root
``pyproject.toml``) instead of repeating them across per-project
``requirements.txt`` files.

Install what a chapter needs::

    pip install -e ".[ch1]"     # chapter 1, no GPU stack
    pip install -e ".[ch7]"     # heavy fine-tuning deps, opt in explicitly

Scope: this package holds *plumbing only* -- provider resolution, environment
loading, trace printing. The teaching code stays inside each chapter's
experiment directory, where a reader can follow it top to bottom.
"""

import os
from pathlib import Path
from dotenv import find_dotenv, load_dotenv

# Automatically find and load repository root .env file
_dotenv_path = find_dotenv(usecwd=True)
if not _dotenv_path:
    _root_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if _root_env.exists():
        _dotenv_path = str(_root_env)

if _dotenv_path:
    load_dotenv(_dotenv_path, override=False)

# Ensure OPENAI_* mirrors LLM_* if not already set
if os.getenv("LLM_BASE_URL") and not os.getenv("OPENAI_BASE_URL"):
    os.environ["OPENAI_BASE_URL"] = os.environ["LLM_BASE_URL"]
if os.getenv("LLM_API_KEY") and not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.environ["LLM_API_KEY"]
if os.getenv("LLM_MODEL") and not os.getenv("OPENAI_MODEL"):
    os.environ["OPENAI_MODEL"] = os.environ["LLM_MODEL"]

__version__ = "0.1.0"

__all__ = ["__version__"]
