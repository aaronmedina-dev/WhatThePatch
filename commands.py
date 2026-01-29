"""
WhatThePatch - CLI Commands

This module contains all the CLI command implementations:
- run_config_test: Test configuration
- show_status: Display current status
- switch_engine/model/output: Interactive switching
- show_prompt/edit_prompt: Prompt management
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests
import yaml

from cli_utils import (
    console,
    print_error,
    print_warning,
    print_success,
    print_info,
    print_panel,
    print_commands,
    create_key_value_table,
    create_status_table,
    format_status,
    format_active,
    format_dim,
    format_highlight,
    format_value,
    get_progress_spinner,
    confirm,
)
from rich.panel import Panel


# Wrapper functions to avoid circular imports with whatthepatch.py
def get_file_path(filename: str) -> Path:
    """Get file path - imports from whatthepatch to avoid circular import at module load."""
    from update import get_file_path as _get_file_path
    return _get_file_path(filename)


def load_config() -> dict:
    """Load config - imports from whatthepatch to avoid circular import at module load."""
    from whatthepatch import load_config as _load_config
    return _load_config()


def _get_version() -> str:
    """Get version string."""
    from whatthepatch import __version__
    return __version__


def _get_install_dir() -> Path:
    """Get install directory."""
    from whatthepatch import INSTALL_DIR
    return INSTALL_DIR


def run_config_test() -> bool:
    """Run configuration tests. Returns True if all pass."""
    console.print()
    console.print("[bold]Testing configuration[/bold]")

    config_path = get_file_path("config.yaml")
    if not config_path.exists():
        print_error(
            "Config file not found",
            [f"Expected at: {config_path}", "Run 'python setup.py' to configure."]
        )
        return False

    config = load_config()
    results = []  # List of (check_name, passed, details)

    # Test config file
    results.append(("Config file", True, str(config_path)))

    # Test all AI engines and mark active one
    active_engine = config.get("engine", "claude-api")
    engine_results = []  # Separate list for engine results

    with get_progress_spinner() as progress:
        task = progress.add_task("Testing AI engines...", total=None)

        try:
            from engines import get_engine, list_engines, EngineError

            available_engines = list_engines()

            for engine_name in available_engines:
                progress.update(task, description=f"Testing {engine_name}...")

                # Check basic config status first (CLI availability, API key presence)
                is_configured, status_msg = get_engine_config_status(engine_name, config)
                model = get_engine_model(engine_name, config)

                if not is_configured:
                    # Not configured - show as skipped/unavailable
                    engine_results.append((engine_name, None, status_msg, engine_name == active_engine, model))
                else:
                    # Configured - test actual connection
                    try:
                        engine = get_engine(engine_name, config)
                        is_valid, error = engine.validate_config()
                        if not is_valid:
                            engine_results.append((engine_name, False, error, engine_name == active_engine, model))
                        else:
                            success, error = engine.test_connection()
                            if success:
                                engine_results.append((engine_name, True, "Ready", engine_name == active_engine, model))
                            else:
                                engine_results.append((engine_name, False, error or "Connection failed", engine_name == active_engine, model))
                    except EngineError as e:
                        engine_results.append((engine_name, False, str(e), engine_name == active_engine, model))

        except ImportError as e:
            results.append(("AI Engines", False, f"Module error: {e}"))

        # Test GitHub token
        progress.update(task, description="Testing GitHub token...")
        github_token = config.get("tokens", {}).get("github", "")
        if github_token:
            try:
                response = requests.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"token {github_token}"},
                    timeout=10,
                )
                if response.status_code == 200:
                    results.append(("GitHub token", True, f"Valid ({github_token[:8]}...)"))
                else:
                    results.append(("GitHub token", False, "Invalid or expired"))
            except Exception:
                results.append(("GitHub token", False, "Connection failed"))
        else:
            results.append(("GitHub token", None, "Not configured"))

        # Test Bitbucket credentials
        # Note: We use /workspaces endpoint as it works with repository-level permissions
        # The /user endpoint requires Account:Read which many app passwords don't have
        progress.update(task, description="Testing Bitbucket credentials...")
        bb_username = config.get("tokens", {}).get("bitbucket_username", "")
        bb_password = config.get("tokens", {}).get("bitbucket_app_password", "")
        if bb_username and bb_password:
            try:
                response = requests.get(
                    "https://api.bitbucket.org/2.0/workspaces",
                    auth=(bb_username, bb_password),
                    timeout=10,
                )
                if response.status_code == 200:
                    results.append(("Bitbucket credentials", True, f"Valid ({bb_username})"))
                elif response.status_code == 401:
                    results.append(("Bitbucket credentials", False, "Invalid or expired"))
                else:
                    # Other errors (403, etc.) - credentials work but may have limited permissions
                    results.append(("Bitbucket credentials", True, f"Valid ({bb_username}, limited scope)"))
            except Exception:
                results.append(("Bitbucket credentials", False, "Connection failed"))
        else:
            results.append(("Bitbucket credentials", None, "Not configured"))

        # Test output directory
        progress.update(task, description="Testing output directory...")
        output_dir = Path(config.get("output", {}).get("directory", "~/pr-reviews")).expanduser()
        if output_dir.exists():
            results.append(("Output directory", True, f"{output_dir}"))
        else:
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                results.append(("Output directory", True, f"Created {output_dir}"))
            except Exception as e:
                results.append(("Output directory", False, str(e)))

        # Test prompt file
        progress.update(task, description="Testing prompt template...")
        prompt_path = get_file_path("prompt.md")
        if prompt_path.exists():
            size = prompt_path.stat().st_size
            results.append(("Prompt template", True, f"{size / 1024:.1f} KB"))
        else:
            results.append(("Prompt template", False, "Not found"))

    # Display results table
    table = create_status_table(["Check", "Status", "Details"])
    passed = 0
    failed = 0

    for check, status, details in results:
        if status is True:
            status_text = "[green]PASS[/green]"
            passed += 1
        elif status is False:
            status_text = "[red]FAIL[/red]"
            failed += 1
        else:
            status_text = "[dim]SKIP[/dim]"
        table.add_row(check, status_text, format_dim(details) if details else "")

    console.print(table)

    # Display AI Engines table
    if engine_results:
        console.print()
        console.print("[bold]AI Engines[/bold]")
        engine_table = create_status_table(["Engine", "Model", "Status", "Details"])

        active_engine_passed = False
        for engine_name, status, details, is_active, model in engine_results:
            # Format engine name with active marker
            if is_active:
                name_display = f"[bold]{engine_name}[/bold] [cyan](active)[/cyan]"
            else:
                name_display = engine_name

            if status is True:
                status_text = "[green]PASS[/green]"
                if is_active:
                    active_engine_passed = True
            elif status is False:
                status_text = "[red]FAIL[/red]"
            else:
                status_text = "[dim]SKIP[/dim]"

            engine_table.add_row(name_display, format_dim(model), status_text, format_dim(details) if details else "")

        console.print(engine_table)

        # Count active engine in pass/fail
        if active_engine_passed:
            passed += 1
        else:
            # Check if active engine failed (not just skipped)
            for engine_name, status, details, is_active, model in engine_results:
                if is_active and status is False:
                    failed += 1
                    break

    console.print()

    if failed == 0:
        console.print(f"[green]All {passed} checks passed![/green]")
    else:
        console.print(f"[yellow]{failed} check(s) failed.[/yellow] Run [cyan]wtp --status[/cyan] for details.")

    return failed == 0


def show_status():
    """Display current configuration status."""
    console.print()

    # Check if config exists
    config_path = get_file_path("config.yaml")
    if not config_path.exists():
        print_error(
            "Config file not found",
            [f"Expected at: {config_path}", "Run 'python setup.py' to configure."]
        )
        return

    config = load_config()

    # Active engine panel
    engine_name = config.get("engine", "claude-api")
    engine_table = create_key_value_table()

    try:
        from engines import get_engine, list_engines, EngineError

        available = list_engines()
        available_display = ", ".join(
            format_active(e) if e == engine_name else e for e in available
        )

        engine_table.add_row("Engine", format_value(engine_name, "success"))
        engine_table.add_row("Available", available_display)

        engine_config = config.get("engines", {}).get(engine_name, {})
        if engine_name == "claude-api":
            api_key = engine_config.get("api_key", "")
            if api_key and not api_key.startswith("sk-ant-api03-..."):
                engine_table.add_row("API Key", f"Configured {format_dim(f'({api_key[:12]}...)')}")
            else:
                engine_table.add_row("API Key", format_value("Not configured", "warning"))
            engine_table.add_row("Model", engine_config.get('model', 'claude-sonnet-4-20250514'))
            engine_table.add_row("Max Tokens", str(engine_config.get('max_tokens', 4096)))
        elif engine_name == "claude-cli":
            cli_path = engine_config.get("path", "")
            engine_table.add_row("CLI Path", cli_path if cli_path else format_dim("System PATH (default)"))
            args = engine_config.get("args", [])
            if args:
                engine_table.add_row("Extra Args", format_highlight(" ".join(args)))
        elif engine_name == "openai-api":
            api_key = engine_config.get("api_key", "")
            if api_key and not api_key.startswith("sk-..."):
                engine_table.add_row("API Key", f"Configured {format_dim(f'({api_key[:12]}...)')}")
            else:
                engine_table.add_row("API Key", format_value("Not configured", "warning"))
            engine_table.add_row("Model", engine_config.get('model', 'gpt-4o'))
            engine_table.add_row("Max Tokens", str(engine_config.get('max_tokens', 4096)))
        elif engine_name == "openai-codex-cli":
            cli_path = engine_config.get("path", "")
            engine_table.add_row("CLI Path", cli_path if cli_path else format_dim("System PATH (default)"))
            engine_table.add_row("Model", engine_config.get('model', 'gpt-5'))
            api_key = engine_config.get("api_key", "")
            if api_key:
                engine_table.add_row("API Key", f"Configured {format_dim(f'({api_key[:12]}...)')}")
            else:
                engine_table.add_row("API Key", format_dim("Using ChatGPT sign-in"))
        elif engine_name == "gemini-api":
            api_key = engine_config.get("api_key", "")
            if api_key and not api_key.startswith("AIza..."):
                engine_table.add_row("API Key", f"Configured {format_dim(f'({api_key[:12]}...)')}")
            else:
                engine_table.add_row("API Key", format_value("Not configured", "warning"))
            engine_table.add_row("Model", engine_config.get('model', 'gemini-2.0-flash'))
            engine_table.add_row("Max Tokens", str(engine_config.get('max_tokens', 4096)))
        elif engine_name == "gemini-cli":
            cli_path = engine_config.get("path", "")
            engine_table.add_row("CLI Path", cli_path if cli_path else format_dim("System PATH (default)"))
            engine_table.add_row("Model", engine_config.get('model', 'gemini-2.0-flash'))
            api_key = engine_config.get("api_key", "")
            if api_key:
                engine_table.add_row("API Key", f"Configured {format_dim(f'({api_key[:12]}...)')}")
            else:
                engine_table.add_row("API Key", format_dim("Using Google auth"))

        # Validate engine
        try:
            engine = get_engine(engine_name, config)
            is_valid, error = engine.validate_config()
            if is_valid:
                engine_table.add_row("Status", format_value("Ready", "success"))
            else:
                engine_table.add_row("Status", format_value(f"Error: {error}", "error"))
        except EngineError as e:
            engine_table.add_row("Status", format_value(f"Error: {e}", "error"))

    except ImportError as e:
        engine_table.add_row("Status", format_value(f"Module error: {e}", "error"))

    console.print(Panel(engine_table, title="[bold]AI Engine[/bold]", border_style="green"))

    # Repository access panel
    repo_table = create_key_value_table()
    tokens = config.get("tokens", {})

    github_token = tokens.get("github", "")
    if github_token:
        repo_table.add_row("GitHub", f"{format_value('Configured', 'success')} {format_dim(f'({github_token[:8]}...)')}")
    else:
        repo_table.add_row("GitHub", format_value("Not configured", "warning"))

    bb_user = tokens.get("bitbucket_username", "")
    bb_pass = tokens.get("bitbucket_app_password", "")
    if bb_user and bb_pass:
        repo_table.add_row("Bitbucket", f"{format_value('Configured', 'success')} {format_dim(f'({bb_user})')}")
    else:
        repo_table.add_row("Bitbucket", format_value("Not configured", "warning"))

    console.print(Panel(repo_table, title="[bold]Repository Access[/bold]", border_style="blue"))

    # Output settings panel
    output_table = create_key_value_table()
    output = config.get("output", {})
    output_dir = output.get("directory", "~/pr-reviews")
    output_format = output.get('format', 'html').upper()

    output_table.add_row("Directory", output_dir)
    output_table.add_row("Format", format_value(output_format, "magenta"))
    output_table.add_row("Auto-open", format_value("Yes", "success") if output.get('auto_open', True) else format_dim("No"))
    output_table.add_row("Pattern", format_dim(output.get('filename_pattern', '{repo}-{pr_number}.md')))

    console.print(Panel(output_table, title="[bold]Output Settings[/bold]", border_style="magenta"))

    # Installation panel
    install_table = create_key_value_table()
    __version__ = _get_version()
    INSTALL_DIR = _get_install_dir()
    install_table.add_row("Version", f"v{__version__}")
    install_table.add_row("Config", str(config_path))
    install_table.add_row("Install Dir", str(INSTALL_DIR))
    if INSTALL_DIR.exists():
        install_table.add_row("Mode", format_value("Installed CLI", "success"))
    else:
        install_table.add_row("Mode", format_dim("Running from source"))

    console.print(Panel(install_table, title="[bold]Installation[/bold]", border_style="dim"))

    # Quick commands
    print_commands([
        ("wtp --switch-engine", "Switch AI engine"),
        ("wtp --switch-model", "Switch AI model"),
        ("wtp --switch-output", "Switch format (html/md/txt)"),
        ("wtp --test-config", "Test configuration"),
        ("wtp --edit-prompt", "Customize review prompt"),
    ])


def get_engine_config_status(engine_name: str, config: dict) -> tuple[bool, str]:
    """Check if an engine is configured and return status message."""
    engine_config = config.get("engines", {}).get(engine_name, {})

    if engine_name == "claude-api":
        api_key = engine_config.get("api_key", "")
        if api_key and not api_key.startswith("sk-ant-api03-..."):
            return True, f"API key configured"
        return False, "API key not configured"

    elif engine_name == "claude-cli":
        # CLI doesn't need much config, just check if claude is available
        cli_path = engine_config.get("path", "") or shutil.which("claude")
        if cli_path:
            return True, f"CLI available"
        return False, "claude command not found"

    elif engine_name == "openai-api":
        api_key = engine_config.get("api_key", "")
        if api_key and not api_key.startswith("sk-..."):
            return True, f"API key configured"
        return False, "API key not configured"

    elif engine_name == "openai-codex-cli":
        # CLI engines are ready if the CLI tool is available on the system
        # No config.yaml setup required if CLI is installed and authenticated
        cli_path = engine_config.get("path", "") or shutil.which("codex")
        if cli_path:
            return True, "CLI available"
        return False, "codex command not found"

    elif engine_name == "gemini-api":
        api_key = engine_config.get("api_key", "")
        if api_key and not api_key.startswith("AIza..."):
            return True, "API key configured"
        return False, "API key not configured"

    elif engine_name == "gemini-cli":
        # CLI engines are ready if the CLI tool is available on the system
        # No config.yaml setup required if CLI is installed and authenticated
        cli_path = engine_config.get("path", "") or shutil.which("gemini")
        if cli_path:
            return True, "CLI available"
        return False, "gemini command not found"

    elif engine_name == "ollama":
        # Check if Ollama server is running
        host = engine_config.get("host", "localhost:11434")
        if not host.startswith("http"):
            host = f"http://{host}"
        try:
            response = requests.get(f"{host}/api/tags", timeout=2)
            if response.status_code == 200:
                model = engine_config.get("model", "codellama")
                return True, f"Server running (model: {model})"
            return False, "Server not responding"
        except requests.exceptions.ConnectionError:
            return False, "Not running (start with: ollama serve)"
        except Exception:
            return False, "Connection failed"

    return False, "Unknown engine"


# Default models for each engine (must match engine implementations)
ENGINE_DEFAULT_MODELS = {
    "claude-api": "claude-sonnet-4-20250514",
    "claude-cli": None,  # Claude CLI uses its own configured model
    "openai-api": "gpt-4o",
    "openai-codex-cli": "gpt-5",
    "gemini-api": "gemini-2.0-flash",
    "gemini-cli": "gemini-2.0-flash",
    "ollama": "codellama",
}


def get_engine_model(engine_name: str, config: dict) -> str:
    """Get the configured model for an engine, or its default."""
    engine_config = config.get("engines", {}).get(engine_name, {})

    if engine_name == "claude-cli":
        # Claude CLI doesn't have a model setting in config
        # It uses whatever model is configured in Claude CLI itself
        # Check if --model is passed via args
        args = engine_config.get("args", [])
        if args and "--model" in args:
            try:
                model_idx = args.index("--model")
                if model_idx + 1 < len(args):
                    return args[model_idx + 1]
            except (ValueError, IndexError):
                pass
        return "(uses CLI default)"

    default_model = ENGINE_DEFAULT_MODELS.get(engine_name, "unknown")
    return engine_config.get("model", default_model)


def get_available_models(engine_name: str, config: dict) -> list[str]:
    """
    Get available models for an engine from config.yaml.

    Users can customize the available_models list in their config.yaml.
    Falls back to built-in defaults if not configured.

    Returns list of model IDs.
    """
    # Check if user has configured available_models in config.yaml
    engine_config = config.get("engines", {}).get(engine_name, {})
    user_models = engine_config.get("available_models", [])

    if user_models:
        return user_models

    # Fallback to built-in defaults if not configured
    default_models = {
        "claude-api": [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
        ],
        "claude-cli": [
            "opus",
            "sonnet",
            "haiku",
        ],
        "openai-api": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "o1",
            "o1-mini",
        ],
        "openai-codex-cli": [
            "gpt-5",
            "gpt-4o",
            "o1",
        ],
        "gemini-api": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-thinking-exp",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
        "gemini-cli": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-thinking-exp",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
    }
    return default_models.get(engine_name, [])


def switch_engine():
    """Interactive engine switcher."""
    console.print()

    # Check if config exists
    config_path = get_file_path("config.yaml")
    if not config_path.exists():
        print_error(
            "Config file not found",
            [f"Expected at: {config_path}", "Run 'python setup.py' to configure."]
        )
        return

    config = load_config()
    current_engine = config.get("engine", "claude-api")

    try:
        from engines import list_engines
        available_engines = list_engines()
    except ImportError:
        print_error("Could not load engines module", ["Run 'python setup.py' to reinstall."])
        return

    # Build engine status table
    engine_status = {}
    table = create_status_table(["#", "Engine", "Model", "Status", "Details"])

    for i, engine_name in enumerate(available_engines, 1):
        is_configured, status_msg = get_engine_config_status(engine_name, config)
        engine_status[engine_name] = is_configured
        model = get_engine_model(engine_name, config)

        # Format engine name
        if engine_name == current_engine:
            name_display = format_active(engine_name)
            status_display = format_value("Active", "success")
        elif is_configured:
            name_display = engine_name
            status_display = format_value("Ready", "success")
        else:
            name_display = engine_name
            status_display = format_value("Not configured", "warning")

        table.add_row(str(i), name_display, format_dim(model), status_display, format_dim(status_msg))

    console.print(table)
    console.print()
    console.print(format_dim("Enter number to switch, 's' for setup, 'm' to change model, or 'q' to quit:"))

    try:
        while True:
            choice = console.input("[cyan]> [/cyan]").strip().lower()

            if choice == 'q':
                console.print(format_dim("No changes made."))
                return

            if choice == 's':
                console.print(f"\nRun [cyan]python setup.py[/cyan] to set up a new engine.")
                return

            if choice == 'm':
                console.print(f"\nRun [cyan]wtp --switch-model[/cyan] to change the model for the active engine.")
                return

            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(available_engines):
                    selected_engine = available_engines[choice_num - 1]
                    break
                else:
                    console.print(f"[yellow]Enter a number between 1 and {len(available_engines)}[/yellow]")
            except ValueError:
                console.print("[yellow]Invalid input. Enter a number, 's', 'm', or 'q'.[/yellow]")

        # Check if selected engine is configured
        if not engine_status[selected_engine]:
            print_warning(f"{selected_engine} is not fully configured.")
            if not confirm("Switch anyway?"):
                console.print(format_dim("No changes made."))
                return
    except KeyboardInterrupt:
        console.print(format_dim("\nCancelled."))
        return

    # Update config file
    if selected_engine == current_engine:
        console.print(f"\n{selected_engine} is already the active engine.")
        return

    try:
        with open(config_path, 'r') as f:
            config_content = f.read()

        new_content = re.sub(
            r'^(engine:\s*)["\']?[\w-]+["\']?\s*$',
            f'engine: "{selected_engine}"',
            config_content,
            flags=re.MULTILINE
        )

        if new_content == config_content:
            config["engine"] = selected_engine
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        else:
            with open(config_path, 'w') as f:
                f.write(new_content)

        print_success(f"Switched to {selected_engine}", {"Config": str(config_path)})

        if not engine_status[selected_engine]:
            console.print(f"\n[yellow]Remember to configure {selected_engine} in config.yaml[/yellow]")

    except Exception as e:
        print_error(f"Error updating config: {e}", ["Please update config.yaml manually."])


def switch_output():
    """Interactive output format switcher."""
    console.print()

    # Check if config exists
    config_path = get_file_path("config.yaml")
    if not config_path.exists():
        print_error(
            "Config file not found",
            [f"Expected at: {config_path}", "Run 'python setup.py' to configure."]
        )
        return

    config = load_config()
    current_format = config.get("output", {}).get("format", "html")

    available_formats = [
        ("html", "Styled HTML with GitHub-like formatting, opens in browser"),
        ("md", "Markdown format, opens in default text editor"),
        ("txt", "Plain text format, opens in default text editor"),
    ]

    # Build format table
    table = create_status_table(["#", "Format", "Status", "Description"])

    for i, (fmt, description) in enumerate(available_formats, 1):
        if fmt == current_format:
            fmt_display = format_active(fmt.upper())
            status_display = format_value("Active", "success")
        else:
            fmt_display = fmt.upper()
            status_display = format_dim("Available")

        table.add_row(str(i), fmt_display, status_display, format_dim(description))

    console.print(table)
    console.print()
    console.print(format_dim("Enter number to switch, or 'q' to quit:"))

    try:
        while True:
            choice = console.input("[cyan]> [/cyan]").strip().lower()

            if choice == 'q':
                console.print(format_dim("No changes made."))
                return

            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(available_formats):
                    selected_format = available_formats[choice_num - 1][0]
                    break
                else:
                    console.print(f"[yellow]Enter a number between 1 and {len(available_formats)}[/yellow]")
            except ValueError:
                console.print("[yellow]Invalid input. Enter a number or 'q'.[/yellow]")
    except KeyboardInterrupt:
        console.print(format_dim("\nCancelled."))
        return

    # Update config file
    if selected_format == current_format:
        console.print(f"\n{selected_format.upper()} is already the active format.")
        return

    try:
        with open(config_path, 'r') as f:
            config_content = f.read()

        new_content = re.sub(
            r'^(\s*format:\s*)["\']?[\w]+["\']?\s*$',
            f'\\1"{selected_format}"',
            config_content,
            flags=re.MULTILINE
        )

        if new_content == config_content:
            if "output" not in config:
                config["output"] = {}
            config["output"]["format"] = selected_format
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        else:
            with open(config_path, 'w') as f:
                f.write(new_content)

        print_success(f"Switched to {selected_format.upper()}", {"Config": str(config_path)})

    except Exception as e:
        print_error(f"Error updating config: {e}", ["Please update config.yaml manually."])


def switch_model():
    """Interactive model switcher for the active engine."""
    console.print()

    # Check if config exists
    config_path = get_file_path("config.yaml")
    if not config_path.exists():
        print_error(
            "Config file not found",
            [f"Expected at: {config_path}", "Run 'python setup.py' to configure."]
        )
        return

    config = load_config()
    current_engine = config.get("engine", "claude-api")
    current_model = get_engine_model(current_engine, config)

    # Get available models for this engine from config (or defaults)
    available_models = get_available_models(current_engine, config)

    if not available_models:
        print_warning(f"No model options available for {current_engine}")
        console.print(f"\nYou can add models to config.yaml under engines.{current_engine}.available_models")
        return

    console.print(f"[bold]Select model for {current_engine}[/bold]")
    console.print(f"Current model: {format_highlight(current_model)}\n")

    # Build model table
    table = create_status_table(["#", "Model", "Status"])

    for i, model_id in enumerate(available_models, 1):
        if model_id == current_model:
            model_display = format_active(model_id)
            status_display = format_value("Active", "success")
        else:
            model_display = model_id
            status_display = format_dim("Available")

        table.add_row(str(i), model_display, status_display)

    # Add custom option
    table.add_row("c", format_dim("Enter custom model"), format_dim(""))

    console.print(table)
    console.print()
    console.print(format_dim("Enter number to switch, 'c' for custom, or 'q' to quit:"))

    try:
        while True:
            choice = console.input("[cyan]> [/cyan]").strip().lower()

            if choice == 'q':
                console.print(format_dim("No changes made."))
                return

            if choice == 'c':
                # Custom model input
                console.print(format_dim("\nEnter the model name (e.g., gpt-4o, claude-sonnet-4-20250514):"))
                custom_model = console.input("[cyan]Model: [/cyan]").strip()
                if custom_model:
                    selected_model = custom_model
                    break
                else:
                    console.print("[yellow]No model entered. Please try again.[/yellow]")
                    continue

            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(available_models):
                    selected_model = available_models[choice_num - 1]
                    break
                else:
                    console.print(f"[yellow]Enter a number between 1 and {len(available_models)}, 'c', or 'q'[/yellow]")
            except ValueError:
                console.print("[yellow]Invalid input. Enter a number, 'c', or 'q'.[/yellow]")
    except KeyboardInterrupt:
        console.print(format_dim("\nCancelled."))
        return

    # Update config file
    if selected_model == current_model:
        console.print(f"\n{selected_model} is already the active model.")
        return

    try:
        # Handle claude-cli specially - it uses args: ["--model", "..."] format
        if current_engine == "claude-cli":
            if "engines" not in config:
                config["engines"] = {}
            if "claude-cli" not in config["engines"]:
                config["engines"]["claude-cli"] = {}
            config["engines"]["claude-cli"]["args"] = ["--model", selected_model]
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        else:
            # Standard model key update for other engines
            with open(config_path, 'r') as f:
                config_content = f.read()

            # Try to update the model in the specific engine section
            # Pattern: find the engine section and update its model line
            engine_section_pattern = rf'(^\s*{re.escape(current_engine)}:\s*\n(?:.*\n)*?)(^\s*model:\s*)["\']?[^"\'\n]+["\']?(\s*$)'
            new_content = re.sub(
                engine_section_pattern,
                rf'\g<1>\g<2>"{selected_model}"\3',
                config_content,
                flags=re.MULTILINE
            )

            if new_content == config_content:
                # Regex didn't match, update via YAML
                if "engines" not in config:
                    config["engines"] = {}
                if current_engine not in config["engines"]:
                    config["engines"][current_engine] = {}
                config["engines"][current_engine]["model"] = selected_model
                with open(config_path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            else:
                with open(config_path, 'w') as f:
                    f.write(new_content)

        print_success(f"Switched {current_engine} to {selected_model}", {"Config": str(config_path)})

    except Exception as e:
        print_error(f"Error updating config: {e}", ["Please update config.yaml manually."])


def show_prompt():
    """Display the current review prompt template."""
    prompt_path = get_file_path("prompt.md")

    if not prompt_path.exists():
        from cli_utils import print_cli_error
        print_cli_error(
            f"prompt.md not found at [yellow]{prompt_path}[/yellow]",
            hints=["Run 'python setup.py' to install WhatThePatch."]
        )
        sys.exit(1)

    print(f"Prompt file: {prompt_path}\n")
    print("=" * 60)
    print(prompt_path.read_text())
    print("=" * 60)
    print(f"\nTo edit this prompt, run: wtp --edit-prompt")


def edit_prompt():
    """Open the prompt file in the default editor."""
    prompt_path = get_file_path("prompt.md")

    if not prompt_path.exists():
        from cli_utils import print_cli_error
        print_cli_error(
            f"prompt.md not found at [yellow]{prompt_path}[/yellow]",
            hints=["Run 'python setup.py' to install WhatThePatch."]
        )
        sys.exit(1)

    # Determine editor
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")

    if not editor:
        # Try common editors
        for ed in ["code", "nano", "vim", "vi"]:
            if shutil.which(ed):
                editor = ed
                break

    if not editor:
        print(f"No editor found. Please edit manually:")
        print(f"  {prompt_path}")
        sys.exit(1)

    print(f"Opening {prompt_path} in {editor}...")
    try:
        subprocess.run([editor, str(prompt_path)])
    except Exception as e:
        print(f"Error opening editor: {e}")
        print(f"Please edit manually: {prompt_path}")
        sys.exit(1)


def edit_config():
    """Open the config file in the default editor."""
    config_path = get_file_path("config.yaml")

    if not config_path.exists():
        print_error(
            "config.yaml not found",
            [f"Expected at: {config_path}", "Run 'python setup.py' to configure."]
        )
        sys.exit(1)

    # Determine editor
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")

    if not editor:
        # Try common editors
        for ed in ["code", "nano", "vim", "vi"]:
            if shutil.which(ed):
                editor = ed
                break

    if not editor:
        print_info("No editor found. Please edit manually:")
        console.print(f"  [cyan]{config_path}[/cyan]")
        return

    print(f"Opening {config_path} in {editor}...")
    try:
        subprocess.run([editor, str(config_path)])
    except Exception as e:
        print_warning(f"Could not open editor: {e}")
        print_info("Please edit manually:")
        console.print(f"  [cyan]{config_path}[/cyan]")

