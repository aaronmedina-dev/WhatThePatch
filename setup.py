#!/usr/bin/env python3
"""
WhatThePatch Setup Script

Interactive setup wizard that:
1. Installs required dependencies
2. Guides through config.yaml creation
3. Tests the configuration
4. Installs CLI command
"""

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from banner import print_banner


SCRIPT_DIR = Path(__file__).parent
INSTALL_DIR = Path.home() / ".whatthepatch"
CONFIG_PATH = INSTALL_DIR / "config.yaml"
CONFIG_EXAMPLE_PATH = SCRIPT_DIR / "config.example.yaml"
REQUIREMENTS_PATH = SCRIPT_DIR / "requirements.txt"
CLI_NAME = "wtp"

# Files to copy to install directory
INSTALL_FILES = [
    "whatthepatch.py",
    "prompt.md",
    "banner.py",
    "cli_utils.py",
]

# Directories to copy to install directory
INSTALL_DIRS = [
    "engines",
]


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_step(step: int, text: str):
    """Print a step indicator."""
    print(f"\n[Step {step}] {text}")
    print("-" * 40)


def prompt(text: str, default: str = None) -> str:
    """Prompt user for input with optional default."""
    if default:
        result = input(f"{text} [{default}]: ").strip()
        return result if result else default
    return input(f"{text}: ").strip()


def prompt_choice(text: str, choices: list, default: int = 0) -> int:
    """Prompt user to choose from a list."""
    print(text)
    for i, choice in enumerate(choices):
        marker = "(default) " if i == default else ""
        print(f"  {i + 1}. {marker}{choice}")

    while True:
        result = input(f"Enter choice [1-{len(choices)}]: ").strip()
        if not result:
            return default
        try:
            choice = int(result) - 1
            if 0 <= choice < len(choices):
                return choice
        except ValueError:
            pass
        print(f"Please enter a number between 1 and {len(choices)}")


def prompt_yes_no(text: str, default: bool = True) -> bool:
    """Prompt for yes/no."""
    default_str = "Y/n" if default else "y/N"
    result = input(f"{text} [{default_str}]: ").strip().lower()
    if not result:
        return default
    return result in ("y", "yes")


def install_dependencies():
    """Install Python dependencies."""
    print_step(1, "Installing Dependencies")

    if not REQUIREMENTS_PATH.exists():
        print("Error: requirements.txt not found")
        return False

    print("Installing packages from requirements.txt...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_PATH)],
            check=True,
        )
        print("Dependencies installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        return False


def check_claude_cli() -> bool:
    """Check if Claude CLI is installed and accessible."""
    claude_path = shutil.which("claude")
    if claude_path:
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
            )
            version = result.stdout.strip() or result.stderr.strip()
            print(f"Claude CLI found: {claude_path}")
            print(f"Version: {version}")
            return True
        except Exception:
            pass
    return False


def check_codex_cli() -> bool:
    """Check if OpenAI Codex CLI is installed and accessible."""
    codex_path = shutil.which("codex")
    if codex_path:
        try:
            result = subprocess.run(
                ["codex", "--version"],
                capture_output=True,
                text=True,
            )
            version = result.stdout.strip() or result.stderr.strip()
            print(f"Codex CLI found: {codex_path}")
            if version:
                print(f"Version: {version}")
            return True
        except Exception:
            pass
    return False


def test_codex_cli() -> bool:
    """Test Codex CLI with a simple prompt."""
    try:
        result = subprocess.run(
            ["codex", "exec", "Say 'test successful'"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            return True

        # Check for common errors
        output = result.stdout + result.stderr
        if "authentication" in output.lower() or "unauthorized" in output.lower():
            print("Error: Codex CLI authentication issue. Run 'codex' to sign in.")
        else:
            print(f"Error: {output[:200]}")
        return False

    except subprocess.TimeoutExpired:
        print("Error: Codex CLI timed out")
        return False
    except Exception as e:
        print(f"Error testing Codex CLI: {e}")
        return False


def test_api_key(api_key: str) -> bool:
    """Test if an Anthropic API key is valid."""
    try:
        import requests
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hi"}],
            },
            timeout=30,
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Error testing API key: {e}")
        return False


def test_openai_api_key(api_key: str) -> bool:
    """Test if an OpenAI API key is valid."""
    try:
        import requests
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": "gpt-4o-mini",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hi"}],
            },
            timeout=30,
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Error testing OpenAI API key: {e}")
        return False


def test_github_token(token: str) -> bool:
    """Test if a GitHub token is valid."""
    try:
        import requests
        response = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}"},
            timeout=10,
        )
        return response.status_code == 200
    except Exception:
        return False


def test_bitbucket_credentials(username: str, app_password: str) -> bool:
    """Test if Bitbucket credentials are valid."""
    try:
        import requests
        response = requests.get(
            "https://api.bitbucket.org/2.0/user",
            auth=(username, app_password),
            timeout=10,
        )
        return response.status_code == 200
    except Exception:
        return False


def test_claude_cli() -> bool:
    """Test Claude CLI with a simple prompt."""
    import tempfile

    temp_dir = Path(tempfile.mkdtemp(prefix="claude-test-"))
    try:
        # Create settings file
        settings_dir = temp_dir / ".claude"
        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_path = settings_dir / "settings.local.json"
        settings_path.write_text(json.dumps({
            "permissions": {
                "allow": ["Read(./**)"],
                "deny": [],
                "ask": [],
            }
        }))

        # Run claude
        result = subprocess.run(
            ["claude", "-p", "Say 'test successful'", "--output-format", "json"],
            cwd=str(temp_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            try:
                response = json.loads(result.stdout)
                if not response.get("is_error"):
                    return True
            except json.JSONDecodeError:
                pass

        # Check for common errors
        output = result.stdout + result.stderr
        if "Invalid API key" in output:
            print("Error: Invalid API key configured in Claude CLI")
        elif "authentication" in output.lower():
            print("Error: Claude CLI authentication issue")
        else:
            print(f"Error: {output[:200]}")
        return False

    except subprocess.TimeoutExpired:
        print("Error: Claude CLI timed out")
        return False
    except Exception as e:
        print(f"Error testing Claude CLI: {e}")
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def create_config():
    """Interactive config.yaml creation."""
    print_step(3, "Configuration Setup")

    if CONFIG_PATH.exists():
        if not prompt_yes_no("config.yaml already exists. Overwrite?", default=False):
            print("Keeping existing config.yaml")
            return True

    config = {}

    # Engine selection
    print("\nChoose your AI engine:")
    engine_choice = prompt_choice(
        "",
        [
            "claude-api - Anthropic Claude API (requires API key)",
            "claude-cli - Claude Code CLI (uses your existing auth)",
            "openai-api - OpenAI API (requires API key)",
            "openai-codex-cli - OpenAI Codex CLI (uses your ChatGPT auth)",
        ],
        default=1,
    )
    engine_names = ["claude-api", "claude-cli", "openai-api", "openai-codex-cli"]
    config["engine"] = engine_names[engine_choice]

    # Initialize engines section
    config["engines"] = {
        "claude-api": {
            "api_key": "",
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
        },
        "claude-cli": {
            "path": "",
            "args": [],
        },
        "openai-api": {
            "api_key": "",
            "model": "gpt-4o",
            "max_tokens": 4096,
        },
        "openai-codex-cli": {
            "path": "",
            "model": "gpt-5-codex",
            "api_key": "",
        },
    }

    # Configure API key based on selected engine
    if config["engine"] == "claude-api":
        print("\nAnthropic API Key (required)")
        print("Get yours at: https://console.anthropic.com/")
        api_key = prompt("Enter your Anthropic API key")
        config["engines"]["claude-api"]["api_key"] = api_key
    elif config["engine"] == "openai-api":
        print("\nOpenAI API Key (required)")
        print("Get yours at: https://platform.openai.com/api-keys")
        api_key = prompt("Enter your OpenAI API key")
        config["engines"]["openai-api"]["api_key"] = api_key
    elif config["engine"] == "openai-codex-cli":
        print("\nOpenAI Codex CLI will use your existing ChatGPT authentication.")
        print("Make sure you've run 'codex' and signed in first.")
        if prompt_yes_no("Configure an API key instead?", default=False):
            api_key = prompt("Enter your OpenAI API key")
            config["engines"]["openai-codex-cli"]["api_key"] = api_key
    else:
        print("\nClaude CLI will use your existing authentication.")
        if prompt_yes_no("Configure an Anthropic API key as backup?", default=False):
            api_key = prompt("Enter your Anthropic API key")
            config["engines"]["claude-api"]["api_key"] = api_key

    # Tokens section (for repo access)
    config["tokens"] = {}

    # GitHub token
    print("\nGitHub Personal Access Token")
    print("Create at: https://github.com/settings/tokens (scope: repo)")
    github_token = prompt("Enter your GitHub token (or leave empty to skip)", default="")
    config["tokens"]["github"] = github_token

    # Bitbucket credentials
    print("\nBitbucket App Password")
    print("Create at: https://bitbucket.org/account/settings/app-passwords/")
    if prompt_yes_no("Configure Bitbucket credentials?", default=True):
        bb_username = prompt("Bitbucket username")
        bb_password = prompt("Bitbucket app password")
        config["tokens"]["bitbucket_username"] = bb_username
        config["tokens"]["bitbucket_app_password"] = bb_password
    else:
        config["tokens"]["bitbucket_username"] = ""
        config["tokens"]["bitbucket_app_password"] = ""

    # Output settings
    print("\nOutput Settings")
    output_dir = prompt("Directory for review files", default="~/pr-reviews")
    config["output"] = {
        "directory": output_dir,
        "filename_pattern": "{repo}-{pr_number}.md",
    }

    # Ticket extraction
    config["ticket"] = {
        "pattern": "([A-Z]+-\\d+)",
        "fallback": "NO-TICKET",
    }

    # Write config
    try:
        import yaml
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        print(f"\nConfiguration saved to: {CONFIG_PATH}")
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def run_tests():
    """Test the configuration."""
    print_step(4, "Testing Configuration")

    if not CONFIG_PATH.exists():
        print("Error: config.yaml not found. Please run setup first.")
        return False

    try:
        import yaml
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading config: {e}")
        return False

    all_passed = True

    # Test engine
    engine = config.get("engine", "claude-api")
    print(f"\nEngine: {engine}")

    if engine == "claude-api":
        print("\nTesting Anthropic API key...")
        api_key = config.get("engines", {}).get("claude-api", {}).get("api_key", "")
        if api_key and not api_key.startswith("sk-ant-api03-..."):
            if test_api_key(api_key):
                print("  API key is valid")
            else:
                print("  API key is INVALID")
                all_passed = False
        else:
            print("  No API key configured")
            all_passed = False
    elif engine == "claude-cli":
        print("\nTesting Claude CLI...")
        if check_claude_cli():
            if test_claude_cli():
                print("  Claude CLI is working")
            else:
                print("  Claude CLI test FAILED")
                all_passed = False
        else:
            print("  Claude CLI not found")
            all_passed = False
    elif engine == "openai-api":
        print("\nTesting OpenAI API key...")
        api_key = config.get("engines", {}).get("openai-api", {}).get("api_key", "")
        if api_key and not api_key.startswith("sk-..."):
            if test_openai_api_key(api_key):
                print("  API key is valid")
            else:
                print("  API key is INVALID")
                all_passed = False
        else:
            print("  No API key configured")
            all_passed = False
    elif engine == "openai-codex-cli":
        print("\nTesting OpenAI Codex CLI...")
        if check_codex_cli():
            if test_codex_cli():
                print("  Codex CLI is working")
            else:
                print("  Codex CLI test FAILED")
                all_passed = False
        else:
            print("  Codex CLI not found. Install with: npm install -g @openai/codex")
            all_passed = False
    else:
        print(f"\nUnknown engine: {engine}")
        all_passed = False

    # Test GitHub token
    github_token = config.get("tokens", {}).get("github", "")
    if github_token:
        print("\nTesting GitHub token...")
        if test_github_token(github_token):
            print("  GitHub token is valid")
        else:
            print("  GitHub token is INVALID")
            all_passed = False
    else:
        print("\nGitHub token: Not configured (GitHub PRs will not work)")

    # Test Bitbucket credentials
    bb_username = config.get("tokens", {}).get("bitbucket_username", "")
    bb_password = config.get("tokens", {}).get("bitbucket_app_password", "")
    if bb_username and bb_password:
        print("\nTesting Bitbucket credentials...")
        if test_bitbucket_credentials(bb_username, bb_password):
            print("  Bitbucket credentials are valid")
        else:
            print("  Bitbucket credentials are INVALID")
            all_passed = False
    else:
        print("\nBitbucket credentials: Not configured (Bitbucket PRs will not work)")

    # Summary
    print("\n" + "=" * 40)
    if all_passed:
        print("All tests PASSED")
    else:
        print("Some tests FAILED - please check your configuration")

    return all_passed


def install_files():
    """Copy necessary files to ~/.whatthepatch/"""
    print_step(2, "Installing Files")

    # Create install directory
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Install directory: {INSTALL_DIR}")

    # Copy files
    for filename in INSTALL_FILES:
        src = SCRIPT_DIR / filename
        dst = INSTALL_DIR / filename

        if not src.exists():
            print(f"  Warning: {filename} not found in source directory")
            continue

        shutil.copy2(src, dst)
        print(f"  Copied: {filename}")

    # Copy directories
    for dirname in INSTALL_DIRS:
        src = SCRIPT_DIR / dirname
        dst = INSTALL_DIR / dirname

        if not src.exists():
            print(f"  Warning: {dirname}/ not found in source directory")
            continue

        # Remove existing directory to ensure clean copy
        if dst.exists():
            shutil.rmtree(dst)

        shutil.copytree(src, dst)
        print(f"  Copied: {dirname}/")

    print(f"\nFiles installed to {INSTALL_DIR}")
    return True


def get_cli_install_dir() -> Path:
    """Get the best directory to install CLI command."""
    # Prefer ~/.local/bin (standard user bin on Linux/macOS)
    local_bin = Path.home() / ".local" / "bin"

    # Check if ~/.local/bin is in PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    if str(local_bin) in path_dirs:
        return local_bin

    # Check /usr/local/bin (requires sudo usually)
    usr_local_bin = Path("/usr/local/bin")
    if str(usr_local_bin) in path_dirs and os.access(usr_local_bin, os.W_OK):
        return usr_local_bin

    # Default to ~/.local/bin even if not in PATH (we'll warn user)
    return local_bin


def install_cli():
    """Install the wtp CLI command."""
    print_step(5, "Installing CLI Command")

    cli_install_dir = get_cli_install_dir()
    cli_path = cli_install_dir / CLI_NAME
    main_script = INSTALL_DIR / "whatthepatch.py"

    # Create CLI install directory if needed
    cli_install_dir.mkdir(parents=True, exist_ok=True)

    # Create wrapper script pointing to ~/.whatthepatch/
    wrapper_content = f"""#!/bin/bash
# WhatThePatch CLI wrapper
# Installed by setup.py
# Files located at: {INSTALL_DIR}

exec "{sys.executable}" "{main_script}" "$@"
"""

    try:
        cli_path.write_text(wrapper_content)
        # Make executable
        cli_path.chmod(cli_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"Installed: {cli_path}")

        # Check if cli_install_dir is in PATH
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        if str(cli_install_dir) not in path_dirs:
            print(f"\nNote: {cli_install_dir} is not in your PATH.")
            print("Add it to your shell profile (~/.bashrc, ~/.zshrc, etc.):")
            print(f'  export PATH="$PATH:{cli_install_dir}"')
            print("\nThen restart your terminal or run:")
            print(f'  source ~/.zshrc  # or ~/.bashrc')
        else:
            print(f"\nYou can now use: {CLI_NAME} --review <PR_URL>")

        return True
    except PermissionError:
        print(f"Error: Permission denied writing to {cli_path}")
        print("Try running with sudo or choose a different install location.")
        return False
    except Exception as e:
        print(f"Error installing CLI: {e}")
        return False


def uninstall_cli():
    """Uninstall the wtp CLI command and installed files."""
    print_header("Uninstalling WhatThePatch")

    # Remove CLI command from common locations
    cli_locations = [
        Path.home() / ".local" / "bin" / CLI_NAME,
        Path("/usr/local/bin") / CLI_NAME,
    ]

    cli_found = False
    for cli_path in cli_locations:
        if cli_path.exists():
            try:
                cli_path.unlink()
                print(f"Removed CLI: {cli_path}")
                cli_found = True
            except PermissionError:
                print(f"Error: Permission denied removing {cli_path}")
                print("Try running with sudo.")
            except Exception as e:
                print(f"Error removing {cli_path}: {e}")

    if not cli_found:
        print(f"CLI command '{CLI_NAME}' not found in standard locations.")

    # Ask about removing install directory
    if INSTALL_DIR.exists():
        print(f"\nInstall directory found: {INSTALL_DIR}")
        if prompt_yes_no("Remove install directory and all files (including config)?", default=False):
            try:
                shutil.rmtree(INSTALL_DIR)
                print(f"Removed: {INSTALL_DIR}")
            except Exception as e:
                print(f"Error removing {INSTALL_DIR}: {e}")
        else:
            print(f"Keeping {INSTALL_DIR}")
            print("Your config.yaml and prompt.md are preserved.")

    print("\nNote: Installed Python packages were not removed.")
    print("To remove them: pip uninstall anthropic requests pyyaml")

    return cli_found


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="WhatThePatch Setup")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall the CLI command")
    args = parser.parse_args()

    if args.uninstall:
        uninstall_cli()
        return

    print_banner()
    print_header("WhatThePatch Setup")

    print("This wizard will help you set up WhatThePatch.\n")
    print(f"Files will be installed to: {INSTALL_DIR}\n")

    choice = prompt_choice(
        "What would you like to do?",
        [
            "Full setup (recommended)",
            "Install/update files only",
            "Configure only",
            "Test configuration only",
            "Install CLI command only",
        ],
        default=0,
    )

    if choice == 0:  # Full setup
        if not install_dependencies():
            print("\nSetup failed at dependency installation.")
            sys.exit(1)
        if not install_files():
            print("\nSetup failed at file installation.")
            sys.exit(1)
        if not create_config():
            print("\nSetup failed at configuration.")
            sys.exit(1)
        run_tests()
        install_cli()

    elif choice == 1:  # Install files only
        install_dependencies()
        install_files()

    elif choice == 2:  # Configure only
        create_config()

    elif choice == 3:  # Test only
        run_tests()

    elif choice == 4:  # Install CLI only
        install_cli()

    print_header("Setup Complete")
    print(f"Files installed to: {INSTALL_DIR}")
    print(f"You can now delete this repository folder if desired.\n")
    print("Run PR reviews with:")
    print(f"  {CLI_NAME} --review <PR_URL>")
    print("\nCommands:")
    print(f"  {CLI_NAME} --review <URL>        Review a pull request")
    print(f"  {CLI_NAME} --status              Show configuration status")
    print(f"  {CLI_NAME} --test-config         Test your configuration")
    print(f"  {CLI_NAME} --update              Update from repository")
    print(f"  {CLI_NAME} --show-prompt         View the review prompt")
    print(f"  {CLI_NAME} --edit-prompt         Edit the review prompt")
    print(f"  {CLI_NAME} --help                Show help")
    print("\nExample:")
    print(f"  {CLI_NAME} --review https://github.com/owner/repo/pull/123")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)
