"""
Gemini CLI Engine - Google Gemini CLI integration.

Uses the Gemini CLI to generate PR reviews.
Leverages existing Google Cloud authentication or API key.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .base import BaseEngine, EngineError


class GeminiCLIEngine(BaseEngine):
    """
    Engine for Google Gemini CLI.

    Configuration:
        path: Path to gemini executable (default: uses system PATH)
        model: Model to use (default: gemini-2.0-flash)
        api_key: Optional API key (can also use GEMINI_API_KEY env var or Google Cloud auth)
    """

    DEFAULT_MODEL = "gemini-2.0-flash"

    @property
    def name(self) -> str:
        return "Gemini CLI"

    @property
    def description(self) -> str:
        return "Google Gemini CLI (uses existing Google auth)"

    def _get_gemini_path(self) -> str:
        """Get the path to the gemini executable."""
        configured_path = self.config.get("path", "")
        if configured_path:
            return configured_path
        return "gemini"

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Check if Gemini CLI is available."""
        gemini_path = self._get_gemini_path()

        # Check if configured path exists
        if self.config.get("path"):
            if not Path(gemini_path).exists():
                return False, f"Gemini CLI not found at: {gemini_path}"
        else:
            # Check if gemini is in PATH
            if not shutil.which("gemini"):
                return False, "Gemini CLI not found in PATH. Install from: https://github.com/google-gemini/gemini-cli"

        return True, None

    def test_connection(self) -> tuple[bool, Optional[str]]:
        """Test Gemini CLI by running a simple prompt."""
        is_valid, error = self.validate_config()
        if not is_valid:
            return False, error

        gemini_path = self._get_gemini_path()

        try:
            # Build environment with API key if configured
            env = None
            api_key = self.config.get("api_key", "")
            if api_key:
                import os
                env = os.environ.copy()
                env["GEMINI_API_KEY"] = api_key

            # Run a simple test
            result = subprocess.run(
                [gemini_path, "-p", "Say 'test successful'"],
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    return True, None
                return False, "Gemini CLI returned empty response"

            # Check for common errors
            output = result.stdout + result.stderr
            if "authentication" in output.lower() or "unauthorized" in output.lower():
                return False, "Gemini CLI authentication issue. Run 'gemini auth' to sign in or set GEMINI_API_KEY"
            elif "not found" in output.lower():
                return False, "Gemini CLI not properly installed"
            elif "api key" in output.lower():
                return False, "Invalid or missing API key"
            else:
                return False, f"CLI error: {output[:200]}"

        except subprocess.TimeoutExpired:
            return False, "Gemini CLI timed out"
        except FileNotFoundError:
            return False, f"Gemini CLI not found: {gemini_path}"
        except Exception as e:
            return False, f"Test failed: {e}"

    def generate_review(
        self,
        pr_data: dict,
        ticket_id: str,
        prompt_template: str,
        external_context: str = "",
    ) -> str:
        """Generate PR review using Gemini CLI."""
        is_valid, error = self.validate_config()
        if not is_valid:
            raise EngineError(f"Invalid configuration: {error}")

        gemini_path = self._get_gemini_path()
        temp_dir = Path(tempfile.mkdtemp(prefix="pr-review-gemini-"))

        try:
            # Write diff to a file
            diff_file = temp_dir / "diff.patch"
            diff_file.write_text(pr_data["diff"])

            # Write PR metadata to a file
            metadata_file = temp_dir / "pr-metadata.txt"
            metadata_content = f"""PR Title: {pr_data["title"]}
PR URL: {pr_data.get("pr_url", "N/A")}
Author: {pr_data.get("author", "Unknown")}
Ticket ID: {ticket_id}
Source Branch: {pr_data["source_branch"]}
Target Branch: {pr_data["target_branch"]}

PR Description:
{pr_data["description"]}
"""
            metadata_file.write_text(metadata_content)

            # Write the formatted prompt (with all template variables filled in)
            template_file = temp_dir / "review-template.md"
            formatted_prompt = self.build_prompt(pr_data, ticket_id, prompt_template, external_context)
            template_file.write_text(formatted_prompt)

            # Build the prompt for Gemini CLI
            cli_prompt = (
                f"Review the PR diff in {diff_file} following the instructions in {template_file}. "
                f"PR metadata is in {metadata_file}. "
                "Output ONLY the markdown review report, nothing else."
            )

            # Build command
            cmd = [gemini_path, "-p", cli_prompt]

            # Add model if configured
            model = self.config.get("model", self.DEFAULT_MODEL)
            if model:
                cmd.extend(["--model", model])

            # Build environment with API key if configured
            import os
            env = os.environ.copy()
            api_key = self.config.get("api_key", "")
            if api_key:
                env["GEMINI_API_KEY"] = api_key

            # Run Gemini CLI
            result = subprocess.run(
                cmd,
                cwd=str(temp_dir),
                capture_output=True,
                text=True,
                env=env,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise EngineError(f"Gemini CLI failed: {error_msg[:500]}")

            output = result.stdout.strip()
            if not output:
                raise EngineError("Gemini CLI returned empty response")

            return output

        except EngineError:
            raise
        except Exception as e:
            raise EngineError(f"Failed to generate review: {e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
