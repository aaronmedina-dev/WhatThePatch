"""
OpenAI Codex CLI Engine - OpenAI Codex CLI integration.

Uses the OpenAI Codex CLI to generate PR reviews.
Leverages existing authentication (ChatGPT Plus/Pro/Team plans).
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .base import BaseEngine, EngineError


class OpenAICodexCLIEngine(BaseEngine):
    """
    Engine for OpenAI Codex CLI.

    Configuration:
        path: Path to codex executable (default: uses system PATH)
        model: Model to use (default: gpt-5)
        api_key: Optional API key (can also use CODEX_API_KEY env var)
    """

    DEFAULT_MODEL = "gpt-5"

    @property
    def name(self) -> str:
        return "OpenAI Codex CLI"

    @property
    def description(self) -> str:
        return "OpenAI Codex CLI (uses existing ChatGPT auth)"

    def _get_codex_path(self) -> str:
        """Get the path to the codex executable."""
        configured_path = self.config.get("path", "")
        if configured_path:
            return configured_path
        return "codex"

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Check if Codex CLI is available."""
        codex_path = self._get_codex_path()

        # Check if configured path exists
        if self.config.get("path"):
            if not Path(codex_path).exists():
                return False, f"Codex CLI not found at: {codex_path}"
        else:
            # Check if codex is in PATH
            if not shutil.which("codex"):
                return False, "Codex CLI not found in PATH. Install with: npm install -g @openai/codex"

        return True, None

    def _parse_codex_output(self, output: str) -> str:
        """
        Parse Codex CLI output to extract the actual response.

        Codex CLI outputs log lines like:
        [timestamp] OpenAI Codex...
        [timestamp] thinking
        <thinking content>
        [timestamp] codex
        <actual response>
        [timestamp] exec command
        [timestamp] command output
        [timestamp] codex
        <more response>
        [timestamp] tokens used: N

        We want just the response content (after [timestamp] codex lines).
        """
        lines = output.strip().split("\n")
        response_lines = []
        in_response = False

        for line in lines:
            # Check if this is a log line (starts with timestamp pattern)
            timestamp_match = re.match(r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\]\s*(.*)$", line)

            if timestamp_match:
                tag_content = timestamp_match.group(1).strip()

                # "[timestamp] codex" marks start of response content
                if tag_content == "codex":
                    in_response = True
                    continue

                # These tags end response capture
                # - thinking: model reasoning (not the actual answer)
                # - exec: command execution
                # - tokens used: usage stats
                # - OpenAI Codex: header
                # - User instructions: the prompt
                if tag_content.startswith(("thinking", "exec ", "tokens used:",
                                           "OpenAI Codex", "User instructions")):
                    in_response = False
                    continue

                # Command output lines (e.g., "[timestamp] zsh -lc 'ls' succeeded")
                if " succeeded" in tag_content or " failed" in tag_content:
                    in_response = False
                    continue

                # Other timestamp lines - keep current state
                continue

            # Skip header lines (workdir:, model:, etc.)
            if re.match(r"^(workdir|model|provider|approval|sandbox|reasoning):", line):
                continue
            if line.strip() == "--------":
                continue
            # Skip "Shell cwd was reset" messages
            if line.startswith("Shell cwd was reset"):
                continue

            # If we're in the response section, capture the line
            if in_response:
                response_lines.append(line)

        result = "\n".join(response_lines).strip()

        # Strip any "thinking" content that appears before the actual markdown review
        # The review should start with a markdown heading (# PR Review: ...)
        if result and not result.startswith("#"):
            # Find the first markdown heading
            heading_match = re.search(r"^(# .+)$", result, re.MULTILINE)
            if heading_match:
                result = result[heading_match.start():]

        return result

    def test_connection(self) -> tuple[bool, Optional[str]]:
        """Test Codex CLI by running a simple prompt."""
        is_valid, error = self.validate_config()
        if not is_valid:
            return False, error

        codex_path = self._get_codex_path()

        try:
            # Build environment with API key if configured
            env = None
            api_key = self.config.get("api_key", "")
            if api_key:
                import os
                env = os.environ.copy()
                env["CODEX_API_KEY"] = api_key

            # Run a simple test with non-interactive flags
            # -a on-request: sets approval mode to on-request (non-interactive)
            # exec --skip-git-repo-check: allows running outside a git repo
            result = subprocess.run(
                [codex_path, "-a", "on-request", "exec", "--skip-git-repo-check", "Say 'test successful'"],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )

            if result.returncode == 0:
                # Parse the output to verify we got a response
                response = self._parse_codex_output(result.stdout)
                if response:
                    return True, None
                return False, "Codex CLI returned empty response"

            # Check for common errors
            output = result.stdout + result.stderr
            if "authentication" in output.lower() or "unauthorized" in output.lower():
                return False, "Codex CLI authentication issue. Run 'codex' to sign in."
            elif "not found" in output.lower():
                return False, "Codex CLI not properly installed"
            elif "trusted directory" in output.lower():
                return False, "Run from a git repository or use --skip-git-repo-check"
            else:
                return False, f"CLI error: {output[:200]}"

        except subprocess.TimeoutExpired:
            return False, "Codex CLI timed out"
        except FileNotFoundError:
            return False, f"Codex CLI not found: {codex_path}"
        except Exception as e:
            return False, f"Test failed: {e}"

    def generate_review(
        self,
        pr_data: dict,
        ticket_id: str,
        prompt_template: str,
        external_context: str = "",
    ) -> str:
        """Generate PR review using OpenAI Codex CLI."""
        is_valid, error = self.validate_config()
        if not is_valid:
            raise EngineError(f"Invalid configuration: {error}")

        codex_path = self._get_codex_path()
        temp_dir = Path(tempfile.mkdtemp(prefix="pr-review-codex-"))

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

            # Build the prompt for Codex CLI
            cli_prompt = (
                f"Review the PR diff in diff.patch following the instructions in review-template.md. "
                f"PR metadata is in pr-metadata.txt. "
                "Output ONLY the markdown review report, nothing else."
            )

            # Build command with non-interactive flags
            # -a on-request: sets approval mode for non-interactive execution
            # exec --skip-git-repo-check: allows running outside a git repo (temp dirs)
            cmd = [codex_path, "-a", "on-request", "exec", "--skip-git-repo-check"]

            # Add model if configured
            model = self.config.get("model", self.DEFAULT_MODEL)
            if model:
                cmd.extend(["--model", model])

            # Add the prompt
            cmd.append(cli_prompt)

            # Build environment with API key if configured
            import os
            env = os.environ.copy()
            api_key = self.config.get("api_key", "")
            if api_key:
                env["CODEX_API_KEY"] = api_key

            # Run Codex CLI from the temp directory so it can access files
            result = subprocess.run(
                cmd,
                cwd=str(temp_dir),
                capture_output=True,
                text=True,
                env=env,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise EngineError(f"Codex CLI failed: {error_msg[:500]}")

            # Parse the output to extract just the review
            output = self._parse_codex_output(result.stdout)
            if not output:
                raise EngineError("Codex CLI returned empty response")

            return output

        except EngineError:
            raise
        except Exception as e:
            raise EngineError(f"Failed to generate review: {e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
