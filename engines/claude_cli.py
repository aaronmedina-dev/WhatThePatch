"""
Claude CLI Engine - Claude Code CLI integration.

Uses the Claude Code CLI to generate PR reviews.
Leverages existing authentication (team plans, OAuth).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .base import BaseEngine, EngineError


class ClaudeCLIEngine(BaseEngine):
    """
    Engine for Claude Code CLI.

    Configuration:
        path: Path to claude executable (default: uses system PATH)
        args: Additional arguments to pass to claude command
    """

    @property
    def name(self) -> str:
        return "Claude CLI"

    @property
    def description(self) -> str:
        return "Claude Code CLI (uses existing auth)"

    def _get_claude_path(self) -> str:
        """Get the path to the claude executable."""
        configured_path = self.config.get("path", "")
        if configured_path:
            return configured_path
        return "claude"

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Check if Claude CLI is available."""
        claude_path = self._get_claude_path()

        # Check if configured path exists
        if self.config.get("path"):
            if not Path(claude_path).exists():
                return False, f"Claude CLI not found at: {claude_path}"
        else:
            # Check if claude is in PATH
            if not shutil.which("claude"):
                return False, "Claude CLI not found in PATH"

        return True, None

    def test_connection(self) -> tuple[bool, Optional[str]]:
        """Test Claude CLI by running a simple prompt."""
        is_valid, error = self.validate_config()
        if not is_valid:
            return False, error

        claude_path = self._get_claude_path()
        temp_dir = Path(tempfile.mkdtemp(prefix="claude-test-"))

        try:
            # Create settings file for permissions
            self._setup_permissions(temp_dir)

            # Run a simple test
            result = subprocess.run(
                [claude_path, "-p", "Say 'test successful'", "--output-format", "json"],
                cwd=str(temp_dir),
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout)
                    if not response.get("is_error"):
                        return True, None
                    return False, response.get("result", "Unknown error")
                except json.JSONDecodeError:
                    return True, None  # Non-JSON output is okay for test

            # Check for common errors
            output = result.stdout + result.stderr
            if "Invalid API key" in output:
                return False, "Invalid API key configured in Claude CLI"
            elif "authentication" in output.lower():
                return False, "Claude CLI authentication issue"
            else:
                return False, f"CLI error: {output[:200]}"

        except subprocess.TimeoutExpired:
            return False, "Claude CLI timed out"
        except FileNotFoundError:
            return False, f"Claude CLI not found: {claude_path}"
        except Exception as e:
            return False, f"Test failed: {e}"
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _setup_permissions(self, working_dir: Path) -> Path:
        """Create Claude settings file with required permissions."""
        settings_dir = working_dir / ".claude"
        settings_path = settings_dir / "settings.local.json"

        settings = {
            "permissions": {
                "allow": [
                    "Read(./**)",
                    "Edit(./**)",
                    "Bash(find:*)",
                    "Bash(ls:*)",
                ],
                "deny": [],
                "ask": [],
            }
        }

        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")

        return settings_path

    def generate_review(
        self,
        pr_data: dict,
        ticket_id: str,
        prompt_template: str,
        external_context: str = "",
    ) -> str:
        """Generate PR review using Claude Code CLI."""
        is_valid, error = self.validate_config()
        if not is_valid:
            raise EngineError(f"Invalid configuration: {error}")

        claude_path = self._get_claude_path()
        temp_dir = Path(tempfile.mkdtemp(prefix="pr-review-"))

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

            # Set up Claude permissions
            self._setup_permissions(temp_dir)

            # Build the prompt for Claude CLI
            cli_prompt = (
                "Review the PR diff in diff.patch following the instructions in review-template.md. "
                "PR metadata is in pr-metadata.txt. "
                "Output ONLY the markdown review report, nothing else."
            )

            # Build command
            cmd = [
                claude_path,
                "-p", cli_prompt,
                "--output-format", "json",
                "--add-dir", str(temp_dir),
            ]

            # Add extra args from config
            extra_args = self.config.get("args", [])
            if extra_args:
                cmd.extend(extra_args)

            # Run Claude CLI
            result = subprocess.run(
                cmd,
                cwd=str(temp_dir),
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise EngineError(f"Claude CLI failed: {error_msg[:500]}")

            # Parse JSON output
            output = result.stdout.strip()
            try:
                response = json.loads(output)
                if isinstance(response, dict):
                    if response.get("is_error"):
                        raise EngineError(f"Claude error: {response.get('result')}")
                    return response.get("result", output)
                return output
            except json.JSONDecodeError:
                # If not JSON, return raw output
                return output

        except EngineError:
            raise
        except Exception as e:
            raise EngineError(f"Failed to generate review: {e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
