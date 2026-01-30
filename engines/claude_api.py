"""
Claude API Engine - Direct Anthropic API integration.

Uses the Anthropic Python SDK to generate PR reviews.
Requires an Anthropic API key.
"""

from __future__ import annotations

from typing import Optional

from .base import BaseEngine, EngineError


class ClaudeAPIEngine(BaseEngine):
    """
    Engine for Anthropic Claude API.

    Configuration:
        api_key: Anthropic API key (required)
        model: Model name (default: claude-sonnet-4-20250514)
        max_tokens: Maximum response tokens (default: 4096)
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    DEFAULT_MAX_TOKENS = 4096

    @property
    def name(self) -> str:
        return "Claude API"

    @property
    def description(self) -> str:
        return "Direct Anthropic API (requires API key)"

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Check if API key is configured."""
        api_key = self.config.get("api_key", "")

        if not api_key:
            return False, "API key not configured"

        if api_key.startswith("sk-ant-api03-..."):
            return False, "API key is placeholder value"

        return True, None

    def test_connection(self) -> tuple[bool, Optional[str]]:
        """Test API key by making a minimal request."""
        is_valid, error = self.validate_config()
        if not is_valid:
            return False, error

        try:
            import anthropic
        except ImportError:
            return False, "anthropic package not installed. Run: pip install anthropic"

        try:
            client = anthropic.Anthropic(api_key=self.config["api_key"])
            client.messages.create(
                model=self.config.get("model", self.DEFAULT_MODEL),
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True, None
        except anthropic.AuthenticationError:
            return False, "Invalid API key"
        except anthropic.NotFoundError as e:
            model = self.config.get("model", self.DEFAULT_MODEL)
            return False, f"Model not found: {model}. Check available models in config.yaml"
        except anthropic.APIError as e:
            error_str = str(e).lower()
            if "model" in error_str and ("not found" in error_str or "does not exist" in error_str):
                model = self.config.get("model", self.DEFAULT_MODEL)
                return False, f"Model not found: {model}. Check available models in config.yaml"
            return False, f"API error: {e}"
        except Exception as e:
            return False, f"Connection failed: {e}"

    def generate_review(
        self,
        pr_data: dict,
        ticket_id: str,
        prompt_template: str,
        external_context: str = "",
    ) -> str:
        """Generate PR review using Anthropic API."""
        is_valid, error = self.validate_config()
        if not is_valid:
            raise EngineError(f"Invalid configuration: {error}")

        try:
            import anthropic
        except ImportError:
            raise EngineError("anthropic package not installed. Run: pip install anthropic")

        # Build the full prompt
        prompt = self.build_prompt(pr_data, ticket_id, prompt_template, external_context)

        # Get configuration
        api_key = self.config["api_key"]
        model = self.config.get("model", self.DEFAULT_MODEL)
        max_tokens = self.config.get("max_tokens", self.DEFAULT_MAX_TOKENS)

        try:
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text

        except anthropic.AuthenticationError:
            raise EngineError("Invalid API key")
        except anthropic.NotFoundError:
            raise EngineError(f"Model not found: {model}. Run 'wtp --switch-model' to select a valid model or update available_models in config.yaml")
        except anthropic.RateLimitError:
            raise EngineError("Rate limit exceeded. Please try again later.")
        except anthropic.APIError as e:
            error_str = str(e).lower()
            if "model" in error_str and ("not found" in error_str or "does not exist" in error_str):
                raise EngineError(f"Model not found: {model}. Run 'wtp --switch-model' to select a valid model")
            raise EngineError(f"API error: {e}")
        except Exception as e:
            raise EngineError(f"Failed to generate review: {e}")
