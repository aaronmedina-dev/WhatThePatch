"""
Tests for engine detection and configuration functions.

Tests cover:
- get_engine_config_status() - checking if engines are configured
- Engine registry and factory functions
- API key validation (placeholder detection)
"""

import pytest
from unittest.mock import patch

from whatthepatch import get_engine_config_status


class TestGetEngineConfigStatus:
    """Tests for get_engine_config_status() function."""

    # Claude API tests
    def test_claude_api_configured_with_real_key(self, mock_config_full):
        """Claude API should be configured when API key is set."""
        is_configured, msg = get_engine_config_status("claude-api", mock_config_full)
        assert is_configured is True
        assert "API key configured" in msg

    def test_claude_api_not_configured_placeholder_key(self, mock_config_minimal):
        """Claude API should not be configured with placeholder key."""
        is_configured, msg = get_engine_config_status("claude-api", mock_config_minimal)
        assert is_configured is False
        assert "not configured" in msg.lower()

    def test_claude_api_not_configured_empty_key(self, mock_config_empty):
        """Claude API should not be configured with empty key."""
        is_configured, msg = get_engine_config_status("claude-api", mock_config_empty)
        assert is_configured is False
        assert "not configured" in msg.lower()

    # OpenAI API tests
    def test_openai_api_configured_with_real_key(self, mock_config_full):
        """OpenAI API should be configured when API key is set."""
        is_configured, msg = get_engine_config_status("openai-api", mock_config_full)
        assert is_configured is True
        assert "API key configured" in msg

    def test_openai_api_not_configured_placeholder_key(self, mock_config_minimal):
        """OpenAI API should not be configured with placeholder key."""
        is_configured, msg = get_engine_config_status("openai-api", mock_config_minimal)
        assert is_configured is False
        assert "not configured" in msg.lower()

    # Gemini API tests
    def test_gemini_api_configured_with_real_key(self, mock_config_full):
        """Gemini API should be configured when API key is set."""
        is_configured, msg = get_engine_config_status("gemini-api", mock_config_full)
        assert is_configured is True
        assert "API key configured" in msg

    def test_gemini_api_not_configured_placeholder_key(self, mock_config_minimal):
        """Gemini API should not be configured with placeholder key."""
        is_configured, msg = get_engine_config_status("gemini-api", mock_config_minimal)
        assert is_configured is False
        assert "not configured" in msg.lower()

    # CLI engine tests (claude-cli)
    def test_claude_cli_configured_when_available(self, mock_config_full):
        """Claude CLI should be configured when claude command is in PATH."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/claude"
            is_configured, msg = get_engine_config_status("claude-cli", mock_config_full)
            assert is_configured is True
            assert "CLI available" in msg

    def test_claude_cli_not_configured_when_not_found(self, mock_config_full):
        """Claude CLI should not be configured when claude command is not found."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            mock_config_full["engines"]["claude-cli"]["path"] = ""
            is_configured, msg = get_engine_config_status("claude-cli", mock_config_full)
            assert is_configured is False
            assert "not found" in msg.lower()

    def test_claude_cli_uses_custom_path(self, mock_config_full):
        """Claude CLI should use custom path if configured."""
        mock_config_full["engines"]["claude-cli"]["path"] = "/custom/path/claude"
        is_configured, msg = get_engine_config_status("claude-cli", mock_config_full)
        assert is_configured is True
        assert "CLI available" in msg

    # CLI engine tests (openai-codex-cli)
    def test_openai_codex_cli_configured_when_available(self, mock_config_full):
        """OpenAI Codex CLI should be configured when codex command is in PATH."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/codex"
            is_configured, msg = get_engine_config_status("openai-codex-cli", mock_config_full)
            assert is_configured is True
            assert "CLI available" in msg

    def test_openai_codex_cli_not_configured_when_not_found(self, mock_config_full):
        """OpenAI Codex CLI should not be configured when codex command is not found."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            mock_config_full["engines"]["openai-codex-cli"]["path"] = ""
            is_configured, msg = get_engine_config_status("openai-codex-cli", mock_config_full)
            assert is_configured is False
            assert "not found" in msg.lower()

    # CLI engine tests (gemini-cli)
    def test_gemini_cli_configured_when_available(self, mock_config_full):
        """Gemini CLI should be configured when gemini command is in PATH."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/gemini"
            is_configured, msg = get_engine_config_status("gemini-cli", mock_config_full)
            assert is_configured is True
            assert "CLI available" in msg

    def test_gemini_cli_not_configured_when_not_found(self, mock_config_full):
        """Gemini CLI should not be configured when gemini command is not found."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            mock_config_full["engines"]["gemini-cli"]["path"] = ""
            is_configured, msg = get_engine_config_status("gemini-cli", mock_config_full)
            assert is_configured is False
            assert "not found" in msg.lower()

    # Unknown engine tests
    def test_unknown_engine_returns_false(self, mock_config_full):
        """Unknown engine should return not configured."""
        is_configured, msg = get_engine_config_status("nonexistent-engine", mock_config_full)
        assert is_configured is False
        assert "unknown" in msg.lower()


class TestApiKeyPlaceholderDetection:
    """Tests for API key placeholder detection."""

    def test_claude_api_detects_placeholder(self):
        """Should detect Claude API placeholder key pattern."""
        config = {
            "engines": {
                "claude-api": {"api_key": "sk-ant-api03-..."}
            }
        }
        is_configured, _ = get_engine_config_status("claude-api", config)
        assert is_configured is False

    def test_openai_api_detects_placeholder(self):
        """Should detect OpenAI API placeholder key pattern."""
        config = {
            "engines": {
                "openai-api": {"api_key": "sk-..."}
            }
        }
        is_configured, _ = get_engine_config_status("openai-api", config)
        assert is_configured is False

    def test_gemini_api_detects_placeholder(self):
        """Should detect Gemini API placeholder key pattern."""
        config = {
            "engines": {
                "gemini-api": {"api_key": "AIza..."}
            }
        }
        is_configured, _ = get_engine_config_status("gemini-api", config)
        assert is_configured is False

    def test_real_keys_pass_validation(self):
        """Real API keys should pass validation."""
        test_cases = [
            ("claude-api", "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx"),
            ("openai-api", "sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx"),
            ("gemini-api", "AIzaSyAxxxxxxxxxxxxxxxxxxxxxxxx"),
        ]
        for engine, key in test_cases:
            config = {"engines": {engine: {"api_key": key}}}
            is_configured, _ = get_engine_config_status(engine, config)
            assert is_configured is True, f"Real key should pass for {engine}"


class TestEngineRegistry:
    """Tests for engine registry functions."""

    def test_list_engines_returns_all_engines(self):
        """list_engines() should return all available engine names."""
        from engines import list_engines

        engines = list_engines()
        expected = [
            "claude-api",
            "claude-cli",
            "openai-api",
            "openai-codex-cli",
            "gemini-api",
            "gemini-cli",
        ]
        for engine in expected:
            assert engine in engines, f"Missing engine: {engine}"

    def test_get_engine_returns_valid_instance(self, mock_config_full):
        """get_engine() should return engine instance for valid engines."""
        from engines import get_engine

        engine = get_engine("claude-api", mock_config_full)
        assert engine is not None
        assert hasattr(engine, "name")
        assert hasattr(engine, "generate_review")

    def test_get_engine_raises_for_unknown(self, mock_config_full):
        """get_engine() should raise for unknown engine names."""
        from engines import get_engine, EngineError

        with pytest.raises(EngineError):
            get_engine("nonexistent-engine", mock_config_full)


class TestEngineBaseClass:
    """Tests for BaseEngine abstract class."""

    def test_all_engines_have_required_methods(self, mock_config_full):
        """All engines should implement required BaseEngine methods."""
        from engines import list_engines, get_engine

        required_methods = [
            "name",
            "description",
            "validate_config",
            "test_connection",
            "generate_review",
        ]

        for engine_name in list_engines():
            engine = get_engine(engine_name, mock_config_full)
            for method in required_methods:
                assert hasattr(engine, method), f"{engine_name} missing {method}"

    def test_all_engines_have_default_model(self):
        """All API engines should have DEFAULT_MODEL constant."""
        from engines.claude_api import ClaudeAPIEngine
        from engines.openai_api import OpenAIAPIEngine
        from engines.gemini_api import GeminiAPIEngine

        assert hasattr(ClaudeAPIEngine, "DEFAULT_MODEL")
        assert hasattr(OpenAIAPIEngine, "DEFAULT_MODEL")
        assert hasattr(GeminiAPIEngine, "DEFAULT_MODEL")
