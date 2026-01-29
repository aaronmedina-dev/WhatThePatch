"""
WhatThePatch - AI Engines

This module provides pluggable AI engine support for generating PR reviews.
Each engine implements the BaseEngine interface.

Available engines:
- claude-api: Anthropic Claude API (direct)
- claude-cli: Claude Code CLI (uses existing auth)
- openai-api: OpenAI GPT models (direct API)
- openai-codex-cli: OpenAI Codex CLI (uses existing ChatGPT auth)
- gemini-api: Google Gemini API (direct)
- gemini-cli: Google Gemini CLI (uses existing Google auth)
- ollama: Local Ollama models (no API key needed)
"""

from .base import BaseEngine, EngineError
from .claude_api import ClaudeAPIEngine
from .claude_cli import ClaudeCLIEngine
from .openai_api import OpenAIAPIEngine
from .openai_codex_cli import OpenAICodexCLIEngine
from .gemini_api import GeminiAPIEngine
from .gemini_cli import GeminiCLIEngine

# Registry of available engines
ENGINES = {
    "claude-api": ClaudeAPIEngine,
    "claude-cli": ClaudeCLIEngine,
    "openai-api": OpenAIAPIEngine,
    "openai-codex-cli": OpenAICodexCLIEngine,
    "gemini-api": GeminiAPIEngine,
    "gemini-cli": GeminiCLIEngine,
}

# Ollama engine - may be missing in partial updates from older versions
# This is a one-time migration issue; running --update again will fix it
OLLAMA_AVAILABLE = False
try:
    from .ollama_api import OllamaAPIEngine
    ENGINES["ollama"] = OllamaAPIEngine
    OLLAMA_AVAILABLE = True
except ImportError:
    pass


def check_incomplete_installation() -> str | None:
    """
    Check if installation is incomplete (missing files from partial update).
    Returns warning message if incomplete, None if OK.
    """
    if not OLLAMA_AVAILABLE:
        return (
            "Your installation is incomplete - some engine files are missing.\n"
            "This can happen when updating from an older version.\n"
            "\n"
            "To fix this, run:  wtp --update\n"
            "\n"
            "This will download all missing files including Ollama support."
        )
    return None


def get_engine(engine_name: str, config: dict) -> BaseEngine:
    """
    Factory function to get an engine instance by name.

    Args:
        engine_name: Name of the engine (e.g., 'claude-api', 'claude-cli')
        config: Full configuration dictionary

    Returns:
        Configured engine instance

    Raises:
        EngineError: If engine is not found or configuration is invalid
    """
    if engine_name not in ENGINES:
        available = ", ".join(ENGINES.keys())
        raise EngineError(f"Unknown engine: {engine_name}. Available: {available}")

    engine_class = ENGINES[engine_name]
    engine_config = config.get("engines", {}).get(engine_name, {})

    return engine_class(engine_config)


def list_engines() -> list:
    """Return list of available engine names."""
    return list(ENGINES.keys())
