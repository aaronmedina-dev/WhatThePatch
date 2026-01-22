"""
Gemini API Engine - Google Generative AI API integration.

Uses the Google Generative AI Python SDK to generate PR reviews.
Requires a Google AI API key.
"""

from typing import Optional

from .base import BaseEngine, EngineError


class GeminiAPIEngine(BaseEngine):
    """
    Engine for Google Gemini API.

    Configuration:
        api_key: Google AI API key (required)
        model: Model name (default: gemini-2.0-flash)
        max_tokens: Maximum response tokens (default: 4096)
    """

    DEFAULT_MODEL = "gemini-2.0-flash"
    DEFAULT_MAX_TOKENS = 4096

    @property
    def name(self) -> str:
        return "Gemini API"

    @property
    def description(self) -> str:
        return "Direct Google AI API (requires API key)"

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Check if API key is configured."""
        api_key = self.config.get("api_key", "")

        if not api_key:
            return False, "API key not configured"

        if api_key.startswith("AIza..."):
            return False, "API key is placeholder value"

        return True, None

    def test_connection(self) -> tuple[bool, Optional[str]]:
        """Test API key by making a minimal request."""
        is_valid, error = self.validate_config()
        if not is_valid:
            return False, error

        try:
            import google.generativeai as genai
        except ImportError:
            return False, "google-generativeai package not installed. Run: pip install google-generativeai"

        try:
            genai.configure(api_key=self.config["api_key"])
            model = genai.GenerativeModel(self.config.get("model", self.DEFAULT_MODEL))
            model.generate_content("Hi")
            return True, None
        except Exception as e:
            error_str = str(e).lower()
            if "invalid api key" in error_str or "api_key" in error_str:
                return False, "Invalid API key"
            elif "quota" in error_str or "rate" in error_str:
                return False, "API quota exceeded or rate limited"
            elif "not found" in error_str or "does not exist" in error_str:
                model = self.config.get('model', self.DEFAULT_MODEL)
                return False, f"Model not found: {model}. Check available models in config.yaml"
            return False, f"Connection failed: {e}"

    def generate_review(
        self,
        pr_data: dict,
        ticket_id: str,
        prompt_template: str,
        external_context: str = "",
    ) -> str:
        """Generate PR review using Google Gemini API."""
        is_valid, error = self.validate_config()
        if not is_valid:
            raise EngineError(f"Invalid configuration: {error}")

        try:
            import google.generativeai as genai
        except ImportError:
            raise EngineError("google-generativeai package not installed. Run: pip install google-generativeai")

        # Build the full prompt
        prompt = self.build_prompt(pr_data, ticket_id, prompt_template, external_context)

        # Get configuration
        api_key = self.config["api_key"]
        model_name = self.config.get("model", self.DEFAULT_MODEL)
        max_tokens = self.config.get("max_tokens", self.DEFAULT_MAX_TOKENS)

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)

            # Configure generation settings
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
            )

            response = model.generate_content(
                prompt,
                generation_config=generation_config,
            )

            # Handle response
            if response.parts:
                return response.text
            elif response.prompt_feedback:
                raise EngineError(f"Prompt blocked: {response.prompt_feedback}")
            else:
                raise EngineError("Empty response from Gemini API")

        except Exception as e:
            error_str = str(e).lower()
            if "invalid api key" in error_str or "api_key" in error_str:
                raise EngineError("Invalid API key")
            elif "quota" in error_str or "rate" in error_str:
                raise EngineError("API quota exceeded. Please try again later.")
            elif "not found" in error_str or "does not exist" in error_str:
                raise EngineError(f"Model not found: {model_name}. Run 'wtp --switch-model' to select a valid model or update available_models in config.yaml")
            elif "blocked" in error_str or "safety" in error_str:
                raise EngineError(f"Content blocked by safety filters: {e}")
            raise EngineError(f"Failed to generate review: {e}")
