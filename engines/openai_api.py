"""
OpenAI API Engine - Direct OpenAI API integration.

Uses the OpenAI Python SDK to generate PR reviews.
Requires an OpenAI API key.
"""

from typing import Optional

from .base import BaseEngine, EngineError


class OpenAIAPIEngine(BaseEngine):
    """
    Engine for OpenAI API.

    Configuration:
        api_key: OpenAI API key (required)
        model: Model name (default: gpt-4o)
        max_tokens: Maximum response tokens (default: 4096)
    """

    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_MAX_TOKENS = 4096

    @property
    def name(self) -> str:
        return "OpenAI API"

    @property
    def description(self) -> str:
        return "Direct OpenAI API (requires API key)"

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Check if API key is configured."""
        api_key = self.config.get("api_key", "")

        if not api_key:
            return False, "API key not configured"

        if api_key.startswith("sk-..."):
            return False, "API key is placeholder value"

        return True, None

    def test_connection(self) -> tuple[bool, Optional[str]]:
        """Test API key by making a minimal request."""
        is_valid, error = self.validate_config()
        if not is_valid:
            return False, error

        try:
            import openai
        except ImportError:
            return False, "openai package not installed. Run: pip install openai"

        try:
            client = openai.OpenAI(api_key=self.config["api_key"])
            client.chat.completions.create(
                model=self.config.get("model", self.DEFAULT_MODEL),
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True, None
        except openai.AuthenticationError:
            return False, "Invalid API key"
        except openai.NotFoundError as e:
            model = self.config.get("model", self.DEFAULT_MODEL)
            return False, f"Model not found: {model}. Check available models in config.yaml"
        except openai.APIError as e:
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
        """Generate PR review using OpenAI API."""
        is_valid, error = self.validate_config()
        if not is_valid:
            raise EngineError(f"Invalid configuration: {error}")

        try:
            import openai
        except ImportError:
            raise EngineError("openai package not installed. Run: pip install openai")

        # Build the full prompt
        prompt = self.build_prompt(pr_data, ticket_id, prompt_template, external_context)

        # Get configuration
        api_key = self.config["api_key"]
        model = self.config.get("model", self.DEFAULT_MODEL)
        max_tokens = self.config.get("max_tokens", self.DEFAULT_MAX_TOKENS)

        try:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content

        except openai.AuthenticationError:
            raise EngineError("Invalid API key")
        except openai.NotFoundError:
            raise EngineError(f"Model not found: {model}. Run 'wtp --switch-model' to select a valid model or update available_models in config.yaml")
        except openai.RateLimitError:
            raise EngineError("Rate limit exceeded. Please try again later.")
        except openai.APIError as e:
            error_str = str(e).lower()
            if "model" in error_str and ("not found" in error_str or "does not exist" in error_str):
                raise EngineError(f"Model not found: {model}. Run 'wtp --switch-model' to select a valid model")
            raise EngineError(f"API error: {e}")
        except Exception as e:
            raise EngineError(f"Failed to generate review: {e}")
