"""
Tests for model management functions in whatthepatch.py.

Tests cover:
- get_engine_model() - retrieving configured/default models
- get_available_models() - getting model lists from config or defaults
- ENGINE_DEFAULT_MODELS - verifying default model constants
"""

import pytest

from whatthepatch import (
    get_engine_model,
    get_available_models,
    ENGINE_DEFAULT_MODELS,
)


class TestEngineDefaultModels:
    """Tests for ENGINE_DEFAULT_MODELS constant."""

    def test_default_models_contains_all_engines(self):
        """Verify all expected engines have default models defined."""
        expected_engines = [
            "claude-api",
            "claude-cli",
            "openai-api",
            "openai-codex-cli",
            "gemini-api",
            "gemini-cli",
        ]
        for engine in expected_engines:
            assert engine in ENGINE_DEFAULT_MODELS, f"Missing default model for {engine}"

    def test_claude_cli_default_is_none(self):
        """Claude CLI should have None as default (uses CLI's own config)."""
        assert ENGINE_DEFAULT_MODELS["claude-cli"] is None

    def test_api_engines_have_string_defaults(self):
        """API engines should have string model defaults."""
        api_engines = ["claude-api", "openai-api", "gemini-api"]
        for engine in api_engines:
            assert isinstance(ENGINE_DEFAULT_MODELS[engine], str)
            assert len(ENGINE_DEFAULT_MODELS[engine]) > 0


class TestGetEngineModel:
    """Tests for get_engine_model() function."""

    def test_returns_configured_model(self, mock_config_full):
        """Should return model from config when configured."""
        result = get_engine_model("claude-api", mock_config_full)
        assert result == "claude-sonnet-4-20250514"

    def test_returns_default_when_no_config(self, mock_config_empty):
        """Should return default model when engine has no config."""
        result = get_engine_model("claude-api", mock_config_empty)
        assert result == ENGINE_DEFAULT_MODELS["claude-api"]

    def test_returns_default_when_model_not_set(self, mock_config_minimal):
        """Should return default model when model key is not set."""
        # Remove model from config
        del mock_config_minimal["engines"]["claude-api"]["model"]
        result = get_engine_model("claude-api", mock_config_minimal)
        assert result == ENGINE_DEFAULT_MODELS["claude-api"]

    def test_openai_api_returns_configured_model(self, mock_config_full):
        """Should return configured model for OpenAI API."""
        result = get_engine_model("openai-api", mock_config_full)
        assert result == "gpt-4o"

    def test_gemini_api_returns_configured_model(self, mock_config_full):
        """Should return configured model for Gemini API."""
        result = get_engine_model("gemini-api", mock_config_full)
        assert result == "gemini-2.0-flash"

    def test_claude_cli_returns_model_from_args(self, mock_config_full):
        """Should extract model from --model arg for Claude CLI."""
        result = get_engine_model("claude-cli", mock_config_full)
        assert result == "opus"

    def test_claude_cli_returns_default_string_when_no_args(self, mock_config_empty):
        """Should return placeholder string when Claude CLI has no model args."""
        result = get_engine_model("claude-cli", mock_config_empty)
        assert result == "(uses CLI default)"

    def test_claude_cli_returns_default_when_model_not_in_args(self, mock_config_full):
        """Should return placeholder when --model not in args."""
        mock_config_full["engines"]["claude-cli"]["args"] = ["--verbose"]
        result = get_engine_model("claude-cli", mock_config_full)
        assert result == "(uses CLI default)"

    def test_unknown_engine_returns_unknown(self, mock_config_full):
        """Should return 'unknown' for unrecognized engine names."""
        result = get_engine_model("nonexistent-engine", mock_config_full)
        assert result == "unknown"


class TestGetAvailableModels:
    """Tests for get_available_models() function."""

    def test_returns_user_configured_models(self, mock_config_full):
        """Should return models from config.yaml available_models list."""
        result = get_available_models("claude-api", mock_config_full)
        assert result == [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-5-sonnet-20241022",
        ]

    def test_returns_default_models_when_not_configured(self, mock_config_empty):
        """Should return built-in defaults when available_models not in config."""
        result = get_available_models("claude-api", mock_config_empty)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "claude-sonnet-4-20250514" in result

    def test_openai_api_default_models(self, mock_config_empty):
        """Should return built-in defaults for OpenAI API."""
        result = get_available_models("openai-api", mock_config_empty)
        assert isinstance(result, list)
        assert "gpt-4o" in result

    def test_gemini_api_default_models(self, mock_config_empty):
        """Should return built-in defaults for Gemini API."""
        result = get_available_models("gemini-api", mock_config_empty)
        assert isinstance(result, list)
        assert "gemini-2.0-flash" in result

    def test_claude_cli_returns_empty_list(self, mock_config_empty):
        """Claude CLI should return empty list (no model selection)."""
        result = get_available_models("claude-cli", mock_config_empty)
        assert result == []

    def test_returns_empty_for_unknown_engine(self, mock_config_empty):
        """Should return empty list for unknown engine."""
        result = get_available_models("nonexistent-engine", mock_config_empty)
        assert result == []

    def test_user_models_override_defaults(self, mock_config_full):
        """User-configured models should completely override defaults."""
        # Config has only 3 models, not the full default list
        result = get_available_models("claude-api", mock_config_full)
        assert len(result) == 3
        # Default "claude-3-5-haiku-20241022" should not be present
        assert "claude-3-5-haiku-20241022" not in result

    def test_empty_available_models_uses_defaults(self, mock_config_minimal):
        """Empty available_models list should fall back to defaults."""
        mock_config_minimal["engines"]["claude-api"]["available_models"] = []
        result = get_available_models("claude-api", mock_config_minimal)
        # Empty list is falsy, so defaults should be used
        assert len(result) > 0


class TestModelConfigOverride:
    """Tests verifying that config.yaml model overrides engine defaults."""

    def test_config_model_overrides_default(self, mock_config_full):
        """Config model should take precedence over ENGINE_DEFAULT_MODELS."""
        # Set a different model in config
        mock_config_full["engines"]["claude-api"]["model"] = "claude-opus-4-20250514"
        result = get_engine_model("claude-api", mock_config_full)
        assert result == "claude-opus-4-20250514"
        assert result != ENGINE_DEFAULT_MODELS["claude-api"]

    def test_all_api_engines_support_override(self, mock_config_full):
        """All API engines should support model override from config."""
        test_cases = [
            ("claude-api", "custom-claude-model"),
            ("openai-api", "custom-openai-model"),
            ("gemini-api", "custom-gemini-model"),
        ]
        for engine, custom_model in test_cases:
            mock_config_full["engines"][engine]["model"] = custom_model
            result = get_engine_model(engine, mock_config_full)
            assert result == custom_model, f"Override failed for {engine}"
