"""
Ollama API Engine - Local LLM integration via Ollama.

Uses the Ollama REST API to generate PR reviews locally.
No API key required - runs entirely on local machine.
"""

from typing import Optional

import requests

from .base import BaseEngine, EngineError


class OllamaAPIEngine(BaseEngine):
    """
    Engine for Ollama local LLMs.

    Configuration:
        host: Ollama server address (default: localhost:11434)
        model: Model name (default: codellama)
        timeout: Request timeout in seconds (default: 300)
        num_ctx: Context window size (default: model's default)
        system_prompt: Optional system prompt to guide the model
    """

    DEFAULT_HOST = "localhost:11434"
    DEFAULT_MODEL = "codellama"
    DEFAULT_TIMEOUT = 300  # 5 minutes - local models can be slow

    # Default system prompt to help local models follow the output format
    # This significantly improves format compliance for smaller models
    DEFAULT_SYSTEM_PROMPT = """You are a code review assistant. You MUST follow the exact output format specified in the user's instructions.

CRITICAL REQUIREMENTS:
1. Output ONLY valid markdown
2. Follow the EXACT section structure provided (## Summary, ## Issues Found, ## Observations, ## Verdict, etc.)
3. Use the severity emojis exactly as specified (e.g., "### 🔴 Critical:", "### 🟠 High:")
4. Include file paths and line numbers for all issues
5. Always include ALL required sections, even if empty
6. Do NOT add extra commentary outside the specified format
7. Do NOT skip any sections

Your output will be parsed programmatically, so format compliance is essential."""

    # Approximate token limits for common models (conservative estimates)
    # Used for warning users about large diffs
    MODEL_CONTEXT_LIMITS = {
        "codellama": 16384,
        "codellama:7b": 16384,
        "codellama:13b": 16384,
        "codellama:34b": 16384,
        "codellama:latest": 16384,
        "llama3.2": 131072,
        "llama3.2:3b": 131072,
        "llama3.2:latest": 131072,
        "deepseek-coder-v2": 16384,
        "deepseek-coder-v2:lite": 16384,
        "qwen2.5-coder": 32768,
        "qwen2.5-coder:latest": 32768,
        "mistral": 32768,
        "mistral:latest": 32768,
    }

    # Approximate chars per token (for estimation)
    CHARS_PER_TOKEN = 4

    @property
    def name(self) -> str:
        return "Ollama (Local)"

    @property
    def description(self) -> str:
        return "Local LLMs via Ollama (no API key needed)"

    def _get_base_url(self) -> str:
        """Get the base URL for Ollama API."""
        host = self.config.get("host", self.DEFAULT_HOST)
        if not host.startswith("http"):
            host = f"http://{host}"
        return host

    def _get_context_limit(self, model: str) -> int:
        """Get the context limit for a model."""
        # Check exact match first
        if model in self.MODEL_CONTEXT_LIMITS:
            return self.MODEL_CONTEXT_LIMITS[model]
        # Check base model name (without tag)
        base_model = model.split(":")[0]
        if base_model in self.MODEL_CONTEXT_LIMITS:
            return self.MODEL_CONTEXT_LIMITS[base_model]
        # Conservative default for unknown models
        return 8192

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text length."""
        return len(text) // self.CHARS_PER_TOKEN

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Check if Ollama configuration is valid."""
        host = self.config.get("host", self.DEFAULT_HOST)
        if not host:
            return False, "Host not configured"
        return True, None

    def test_connection(self) -> tuple[bool, Optional[str]]:
        """Test connection to Ollama server."""
        model = self.config.get("model", self.DEFAULT_MODEL)
        base_url = self._get_base_url()

        try:
            # Check if server is running
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                return False, f"Ollama server not responding (status {response.status_code})"

            # Check if model is available
            models = response.json().get("models", [])
            model_names = [m.get("name", "").split(":")[0] for m in models]
            full_names = [m.get("name", "") for m in models]

            if model not in model_names and model not in full_names and f"{model}:latest" not in full_names:
                available = ", ".join(model_names[:5]) if model_names else "none"
                return False, f"Model '{model}' not found. Available: {available}. Run: ollama pull {model}"

            return True, None

        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to Ollama. Is it running? Start with: ollama serve"
        except requests.exceptions.Timeout:
            return False, "Connection to Ollama timed out"
        except Exception as e:
            return False, f"Connection failed: {e}"

    def check_context_length(self, prompt: str) -> tuple[bool, Optional[str]]:
        """
        Check if the prompt exceeds the model's context length.

        Returns:
            Tuple of (is_within_limit, warning_message)
        """
        model = self.config.get("model", self.DEFAULT_MODEL)
        context_limit = self._get_context_limit(model)
        estimated_tokens = self._estimate_tokens(prompt)

        # Leave room for response (at least 2048 tokens)
        max_input_tokens = context_limit - 2048

        if estimated_tokens > max_input_tokens:
            return False, (
                f"Input too large for model '{model}' (estimated {estimated_tokens:,} tokens, "
                f"limit ~{max_input_tokens:,} tokens). "
                f"Try: 1) Use a model with larger context (e.g., llama3.2), "
                f"2) Review a smaller PR, or 3) Reduce external context."
            )

        # Warn if close to limit (>80%)
        if estimated_tokens > max_input_tokens * 0.8:
            return True, (
                f"Warning: Input is {estimated_tokens:,} tokens (~{int(estimated_tokens/max_input_tokens*100)}% "
                f"of {model}'s limit). Response may be truncated."
            )

        return True, None

    def generate_review(
        self,
        pr_data: dict,
        ticket_id: str,
        prompt_template: str,
        external_context: str = "",
    ) -> str:
        """Generate PR review using Ollama."""
        is_valid, error = self.validate_config()
        if not is_valid:
            raise EngineError(f"Invalid configuration: {error}")

        # Build the full prompt
        prompt = self.build_prompt(pr_data, ticket_id, prompt_template, external_context)

        # Check context length before sending
        within_limit, message = self.check_context_length(prompt)
        if not within_limit:
            raise EngineError(message)
        # Note: Warning message could be logged here if we add logging

        # Get configuration
        base_url = self._get_base_url()
        model = self.config.get("model", self.DEFAULT_MODEL)
        timeout = self.config.get("timeout", self.DEFAULT_TIMEOUT)
        num_ctx = self.config.get("num_ctx")  # Optional context window override

        # Use configured system prompt, or default if not set
        # The default helps local models follow the output format better
        system_prompt = self.config.get("system_prompt")
        if system_prompt is None:
            system_prompt = self.DEFAULT_SYSTEM_PROMPT

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request payload
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        # Add options if num_ctx is specified
        if num_ctx:
            payload["options"] = {"num_ctx": num_ctx}

        try:
            response = requests.post(
                f"{base_url}/api/chat",
                json=payload,
                timeout=timeout,
            )

            if response.status_code != 200:
                error_text = response.text
                # Check for context length error from Ollama
                if "context" in error_text.lower() and "length" in error_text.lower():
                    raise EngineError(
                        f"Input exceeds model context length. "
                        f"Try a model with larger context or reduce the diff size."
                    )
                raise EngineError(f"Ollama API error: {response.status_code} - {error_text}")

            result = response.json()
            return result.get("message", {}).get("content", "")

        except requests.exceptions.ConnectionError:
            raise EngineError("Cannot connect to Ollama. Is it running? Start with: ollama serve")
        except requests.exceptions.Timeout:
            raise EngineError(
                f"Request timed out after {timeout}s. This can happen with large PRs on slower hardware. "
                f"Options: 1) Increase timeout in config, 2) Use a smaller/faster model, "
                f"3) Enable GPU acceleration for faster inference."
            )
        except EngineError:
            raise
        except Exception as e:
            raise EngineError(f"Failed to generate review: {e}")
