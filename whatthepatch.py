#!/usr/bin/env python3
"""
WhatThePatch - PR Helper Tool

A CLI tool to automatically generate PR reviews using AI.
Supports GitHub and Bitbucket pull requests.
Supports multiple AI engines (Claude API, Claude CLI, OpenAI API, OpenAI Codex CLI).

Usage:
    wtp --review <PR_URL>

Example:
    wtp --review https://github.com/owner/repo/pull/123
    wtp --review https://bitbucket.org/workspace/repo/pull-requests/456
"""

from __future__ import annotations

__version__ = "1.3.3"

import argparse
import re
import sys
from pathlib import Path

# Track missing dependencies for helpful error messages
_MISSING_DEPS = []

try:
    import requests
except ImportError:
    _MISSING_DEPS.append("requests")

try:
    import yaml
except ImportError:
    _MISSING_DEPS.append("pyyaml")

try:
    import html2text
except ImportError:
    _MISSING_DEPS.append("html2text")

# Check for missing dependencies before proceeding
if _MISSING_DEPS:
    print("\n[Error] Missing required dependencies:", ", ".join(_MISSING_DEPS))
    print("\nTo install missing dependencies, run one of:")
    print("  pip install " + " ".join(_MISSING_DEPS))
    print("  pip install -r requirements.txt")
    print("  python setup.py  (interactive setup wizard)")
    print("\nIf you recently ran --update, new dependencies may have been added.")
    print("Run 'pip install -r requirements.txt' to install them.\n")
    sys.exit(1)

from banner import print_banner
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

# URL and context handling
from url_context import (
    is_url,
    read_context_paths,
    format_context_content,
    check_context_size,
    fetch_url_content,
    get_github_token,
    get_bitbucket_credentials,
    CONTEXT_SIZE_WARNING_THRESHOLD,
    EXCLUDED_DIRS,
    BINARY_EXTENSIONS,
)

# PR providers - GitHub and Bitbucket
from pr_providers import (
    parse_pr_url,
    fetch_github_pr,
    fetch_bitbucket_pr,
    extract_ticket_id,
    sanitize_filename,
)

# CLI commands
from commands import (
    run_config_test,
    show_status,
    get_engine_config_status,
    get_engine_model,
    get_available_models,
    switch_engine,
    switch_output,
    switch_model,
    show_prompt,
    edit_prompt,
    edit_config,
    ENGINE_DEFAULT_MODELS,
)

# Output handling
from output import (
    save_review,
    convert_to_html,
    auto_open_file,
)

# Update system
from update import (
    INSTALL_DIR,
    get_file_path,
    parse_version,
    check_for_updates,
    show_update_notification,
    run_update,
)

# Add install directory to path for engine imports
if INSTALL_DIR.exists():
    sys.path.insert(0, str(INSTALL_DIR))
# Also add script directory for development
sys.path.insert(0, str(Path(__file__).parent))


def load_prompt_template() -> str:
    """Load the review prompt template from prompt.md"""
    prompt_path = get_file_path("prompt.md")

    if not prompt_path.exists():
        from cli_utils import print_cli_error
        print_cli_error(
            f"prompt.md not found at [yellow]{prompt_path}[/yellow]",
            hints=["Run setup.py to install WhatThePatch."]
        )
        sys.exit(1)

    return prompt_path.read_text()


def load_config() -> dict:
    """Load configuration from config.yaml"""
    config_path = get_file_path("config.yaml")

    if not config_path.exists():
        from cli_utils import print_cli_error
        print_cli_error(
            f"config.yaml not found at [yellow]{config_path}[/yellow]",
            hints=["Run setup.py to configure WhatThePatch."]
        )
        sys.exit(1)

    with open(config_path) as f:
        return yaml.safe_load(f)



def generate_review(
    pr_data: dict,
    ticket_id: str,
    config: dict,
    external_context: str = "",
) -> str:
    """Generate PR review using configured engine."""
    try:
        from engines import get_engine, EngineError
    except ImportError as e:
        from cli_utils import print_cli_error
        print_cli_error(
            f"Could not load engines module: [yellow]{e}[/yellow]",
            hints=["Run setup.py to install WhatThePatch properly."]
        )
        sys.exit(1)

    engine_name = config.get("engine", "claude-api")
    prompt_template = load_prompt_template()

    try:
        engine = get_engine(engine_name, config)
        return engine.generate_review(pr_data, ticket_id, prompt_template, external_context)
    except EngineError as e:
        from cli_utils import print_cli_error
        print_cli_error(str(e))
        sys.exit(1)



class WTPArgumentParser(argparse.ArgumentParser):
    """Custom argument parser with improved error formatting."""

    def error(self, message):
        """Display a formatted error message with highlighting."""
        import re
        from rich.console import Console

        # Use a console that writes to stderr with force_terminal for colors
        err_console = Console(stderr=True, force_terminal=True)

        # Highlight the argument name in the error message
        # Pattern matches: argument --foo/-f or argument --foo
        highlighted_message = re.sub(
            r'argument (--[\w-]+(?:/-\w+)?)',
            r'argument [bold yellow]\1[/bold yellow]',
            message
        )
        err_console.print()
        err_console.print(f"[bold red]Error:[/bold red] {highlighted_message}")
        err_console.print()

        # Format usage on a single line for cleaner display
        usage = self.format_usage().replace('usage: ', '').replace('\n', ' ')
        usage = re.sub(r'\s+', ' ', usage).strip()
        err_console.print(f"[dim]Usage:[/dim] [cyan]{usage}[/cyan]", highlight=False)
        err_console.print()
        err_console.print("[dim]Run[/dim] [cyan]wtp --help[/cyan] [dim]for more information.[/dim]")
        err_console.print()
        sys.exit(2)


def main():
    # Show banner for help
    if len(sys.argv) == 1 or "-h" in sys.argv or "--help" in sys.argv:
        print_banner()

    # Check for incomplete installation (missing files from partial update)
    from engines import check_incomplete_installation
    incomplete_warning = check_incomplete_installation()
    if incomplete_warning:
        console.print()
        console.print(Panel(
            incomplete_warning,
            title="[bold yellow]Incomplete Installation[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        ))
        console.print()

    parser = WTPArgumentParser(
        prog="wtp",
        description="WhatThePatch - Generate AI-powered PR reviews",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  wtp --review https://github.com/owner/repo/pull/123
  wtp --review https://bitbucket.org/workspace/repo/pull-requests/456
  wtp --review <URL> --context /path/to/shared-lib
  wtp --review <URL> --context https://github.com/org/repo/blob/main/types.ts
  wtp --review <URL> --dry-run --verbose

Author:
  Aaron Medina
  GitHub:   https://github.com/aaronmedina-dev
  LinkedIn: https://www.linkedin.com/in/aamedina/
""",
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"%(prog)s v{__version__}",
    )

    # Review commands
    review_group = parser.add_argument_group("Review")
    review_group.add_argument(
        "--review", "-r",
        metavar="URL",
        help="Generate a review for the given PR URL",
    )
    review_group.add_argument(
        "--context", "-c",
        action="append",
        metavar="PATH_OR_URL",
        help="Add file, directory, or URL as context (can use multiple times)",
    )
    review_group.add_argument(
        "--format", "-f",
        choices=["md", "txt", "html"],
        metavar="FORMAT",
        help="Output format: html (default), md, or txt",
    )
    review_group.add_argument(
        "--no-open",
        action="store_true",
        help="Don't auto-open the output file after generation",
    )
    review_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be sent to AI without calling it",
    )
    review_group.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including prompt preview",
    )

    # Configuration commands
    config_group = parser.add_argument_group("Configuration")
    config_group.add_argument(
        "--status",
        action="store_true",
        help="Show current configuration and active AI engine",
    )
    config_group.add_argument(
        "--switch-engine",
        action="store_true",
        help="Switch between configured AI engines",
    )
    config_group.add_argument(
        "--switch-model",
        action="store_true",
        help="Switch the AI model for the active engine",
    )
    config_group.add_argument(
        "--switch-output",
        action="store_true",
        help="Switch between output formats (html, md, txt)",
    )
    config_group.add_argument(
        "--test-config",
        action="store_true",
        help="Test all engines and credentials",
    )

    # Prompt commands
    prompt_group = parser.add_argument_group("Prompt")
    prompt_group.add_argument(
        "--show-prompt",
        action="store_true",
        help="Display the current review prompt template",
    )
    prompt_group.add_argument(
        "--edit-prompt",
        action="store_true",
        help="Open the prompt template in your editor",
    )
    prompt_group.add_argument(
        "--edit-config",
        action="store_true",
        help="Open config.yaml in your editor",
    )

    # Utility commands
    util_group = parser.add_argument_group("Utility")
    util_group.add_argument(
        "--update",
        action="store_true",
        help="Update WhatThePatch from the git repository",
    )
    args = parser.parse_args()

    # Handle special commands
    if args.update:
        run_update()
        return

    if args.show_prompt:
        show_prompt()
        return

    if args.edit_prompt:
        edit_prompt()
        return

    if args.edit_config:
        edit_config()
        return

    if args.status:
        show_status()
        show_update_notification()
        return

    if args.switch_engine:
        switch_engine()
        show_update_notification()
        return

    if args.switch_output:
        switch_output()
        show_update_notification()
        return

    if args.switch_model:
        switch_model()
        show_update_notification()
        return

    if args.test_config:
        success = run_config_test()
        show_update_notification()
        sys.exit(0 if success else 1)

    if not args.review:
        parser.print_help()
        sys.exit(1)

    console.print()
    config = load_config()

    # Fetch PR data with progress spinner
    pr_info = None
    pr_data = None

    with get_progress_spinner() as progress:
        task = progress.add_task("Parsing PR URL...", total=None)
        pr_info = parse_pr_url(args.review)

        progress.update(task, description=f"Fetching PR #{pr_info['pr_number']}...")
        if pr_info["platform"] == "github":
            pr_data = fetch_github_pr(
                pr_info["owner"],
                pr_info["repo"],
                pr_info["pr_number"],
                config["tokens"]["github"],
            )
        else:
            pr_data = fetch_bitbucket_pr(
                pr_info["owner"],
                pr_info["repo"],
                pr_info["pr_number"],
                config["tokens"]["bitbucket_username"],
                config["tokens"]["bitbucket_app_password"],
            )

    # Add PR URL to data for template
    pr_data["pr_url"] = args.review

    ticket_id = extract_ticket_id(
        pr_data["source_branch"],
        config["ticket"]["pattern"],
        config["ticket"]["fallback"],
    )

    diff_lines = pr_data["diff"].count("\n")
    diff_size_kb = len(pr_data["diff"].encode('utf-8')) / 1024

    # Display PR info panel
    pr_table = create_key_value_table()
    pr_number = pr_info["pr_number"]
    pr_table.add_row("PR", f"{format_highlight(f'#{pr_number}')} {pr_data['title']}")
    pr_table.add_row("Author", pr_data.get("author", "Unknown"))
    pr_table.add_row("Branch", f"{format_dim(pr_data['source_branch'])} -> {format_dim(pr_data['target_branch'])}")
    pr_table.add_row("Ticket", format_highlight(ticket_id))
    pr_table.add_row("Diff", f"{diff_lines} lines ({diff_size_kb:.1f} KB)")

    console.print(Panel(pr_table, title="[bold]Pull Request[/bold]", border_style="cyan"))

    # Handle external context if provided
    external_context = ""
    context_size = 0
    if args.context:
        with get_progress_spinner() as progress:
            progress.add_task("Reading external context...", total=None)
            external_context, context_size, local_count, url_count = read_context_paths(args.context)

        if context_size > 0:
            context_table = create_key_value_table()
            context_table.add_row("Paths", str(len(args.context)))
            # Show local vs URL breakdown
            if url_count > 0 and local_count > 0:
                context_table.add_row("Sources", f"{local_count} local, {url_count} URL")
            elif url_count > 0:
                context_table.add_row("Sources", f"{url_count} URL")
            else:
                context_table.add_row("Sources", f"{local_count} local")
            context_table.add_row("Size", f"{context_size / 1024:.1f} KB")
            console.print(Panel(context_table, title="[bold]External Context[/bold]", border_style="blue"))

            if not check_context_size(context_size):
                console.print(format_dim("Aborted."))
                sys.exit(0)

    engine_name = config.get("engine", "claude-api")
    try:
        from engines import get_engine
        engine = get_engine(engine_name, config)
        engine_label = engine.name
    except Exception:
        engine_label = engine_name

    # Build the prompt for dry-run or verbose display
    if args.dry_run or args.verbose:
        prompt_template = load_prompt_template()
        context_section = external_context if external_context else "No external context provided."
        full_prompt = prompt_template.format(
            ticket_id=ticket_id,
            pr_title=pr_data["title"],
            pr_url=pr_data.get("pr_url", ""),
            pr_author=pr_data.get("author", "Unknown"),
            source_branch=pr_data["source_branch"],
            target_branch=pr_data["target_branch"],
            pr_description=pr_data["description"],
            diff=pr_data["diff"],
            external_context=context_section,
        )
        prompt_size = len(full_prompt.encode('utf-8'))

        if args.verbose:
            console.print(Panel(
                f"{full_prompt[:3000]}{'...' if len(full_prompt) > 3000 else ''}\n\n"
                f"[dim]({len(full_prompt):,} characters total)[/dim]",
                title="[bold]Prompt Preview[/bold]",
                border_style="yellow"
            ))

        if args.dry_run:
            dry_run_table = create_key_value_table()
            dry_run_table.add_row("Engine", engine_label)
            dry_run_table.add_row("Prompt size", f"{prompt_size:,} bytes ({prompt_size / 1024:.1f} KB)")
            dry_run_table.add_row("Diff lines", str(diff_lines))
            dry_run_table.add_row("External context", f"{context_size / 1024:.1f} KB" if args.context else "None")

            console.print(Panel(dry_run_table, title="[bold yellow]Dry Run[/bold yellow]", border_style="yellow"))
            console.print()
            console.print("[yellow]No API call made.[/yellow] Remove --dry-run to generate review.")
            return

    # Generate review with progress spinner
    review = None
    with get_progress_spinner() as progress:
        progress.add_task(f"Generating review with {engine_label}...", total=None)
        review = generate_review(pr_data, ticket_id, config, external_context)

    # Save review
    output_format = args.format or config.get("output", {}).get("format", "html")
    with get_progress_spinner() as progress:
        progress.add_task(f"Saving review ({output_format})...", total=None)
        output_path = save_review(review, pr_info, ticket_id, pr_data, config, output_format)

    # Success message
    print_success("Review complete!", {
        "Output": str(output_path),
        "Format": output_format.upper()
    })

    # Auto-open file if enabled
    auto_open = config.get("output", {}).get("auto_open", True)
    if auto_open and not args.no_open:
        auto_open_file(output_path)

    # Check for updates
    show_update_notification()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print(format_dim("\n\nOperation cancelled."))
        sys.exit(0)
