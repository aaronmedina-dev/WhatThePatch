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

__version__ = "1.2.1"

import argparse
import json
import time
import os
import platform
import re
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

import hashlib

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
    ENGINE_DEFAULT_MODELS,
)

# Install directory for all WhatThePatch files
INSTALL_DIR = Path.home() / ".whatthepatch"

# Add install directory to path for engine imports
if INSTALL_DIR.exists():
    sys.path.insert(0, str(INSTALL_DIR))
# Also add script directory for development
sys.path.insert(0, str(Path(__file__).parent))


def get_file_path(filename: str) -> Path:
    """Get the path to a file, checking install dir first, then script dir."""
    # Check install directory first
    install_path = INSTALL_DIR / filename
    if install_path.exists():
        return install_path

    # Fall back to script directory (for development)
    script_path = Path(__file__).parent / filename
    if script_path.exists():
        return script_path

    return install_path  # Return install path for error messages


# Update check configuration
GITHUB_REPO = "aaronmedina-dev/WhatThePatch"
UPDATE_CHECK_INTERVAL = 86400  # 24 hours in seconds
UPDATE_CACHE_FILE = Path.home() / ".config" / "whatthepatch" / "update_cache.json"


def get_update_cache() -> dict:
    """Load the update cache from disk."""
    try:
        if UPDATE_CACHE_FILE.exists():
            with open(UPDATE_CACHE_FILE, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def save_update_cache(cache: dict) -> None:
    """Save the update cache to disk."""
    try:
        UPDATE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(UPDATE_CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except IOError:
        pass  # Silently fail if we can't write cache


def parse_version(version_str: str) -> tuple:
    """Parse version string into comparable tuple. Handles 'v' prefix."""
    version_str = version_str.lstrip('v')
    try:
        parts = version_str.split('.')
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return (0, 0, 0)


def check_for_updates() -> tuple[bool, str, str] | None:
    """
    Check if a new version is available.

    Returns:
        Tuple of (update_available, current_version, latest_version) or None if check skipped/failed.
    """
    cache = get_update_cache()
    current_time = time.time()

    # Check if we should skip (checked recently)
    last_check = cache.get("last_check", 0)
    if current_time - last_check < UPDATE_CHECK_INTERVAL:
        # Use cached result if available
        cached_latest = cache.get("latest_version")
        if cached_latest:
            current = parse_version(__version__)
            latest = parse_version(cached_latest)
            if latest > current:
                return (True, __version__, cached_latest)
        return None

    # Fetch latest release from GitHub
    try:
        response = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            timeout=5,
            headers={"Accept": "application/vnd.github.v3+json"}
        )

        if response.status_code == 200:
            data = response.json()
            latest_version = data.get("tag_name", "").lstrip('v')

            # Update cache
            cache["last_check"] = current_time
            cache["latest_version"] = latest_version
            save_update_cache(cache)

            # Compare versions
            current = parse_version(__version__)
            latest = parse_version(latest_version)

            if latest > current:
                return (True, __version__, latest_version)
            return (False, __version__, latest_version)

        elif response.status_code == 404:
            # No releases yet - update cache to avoid repeated checks
            cache["last_check"] = current_time
            cache["latest_version"] = __version__
            save_update_cache(cache)

    except (requests.RequestException, json.JSONDecodeError):
        pass  # Silently fail on network errors

    return None


def show_update_notification() -> None:
    """Check for updates and display notification if available."""
    result = check_for_updates()
    if result and result[0]:  # update_available is True
        _, current, latest = result
        console.print()
        console.print(f"[yellow]Update available:[/yellow] v{current} -> v{latest}  [dim]Run[/dim] [cyan]wtp --update[/cyan] [dim]to upgrade[/dim]")


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


def save_review(
    review: str,
    pr_info: dict,
    ticket_id: str,
    pr_data: dict,
    config: dict,
    output_format: str = "html",
) -> Path:
    """Save review to output directory.

    Args:
        review: The review content (markdown format)
        pr_info: PR information dict
        ticket_id: Extracted ticket ID
        pr_data: PR data dict
        config: Configuration dict
        output_format: Output format - 'md', 'txt', or 'html'

    Returns:
        Path to the saved file
    """
    output_dir = Path(config["output"]["directory"]).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get base filename from pattern (remove any existing extension)
    filename_pattern = config["output"]["filename_pattern"]
    base_filename = filename_pattern.format(
        repo=pr_info["repo"],
        pr_number=pr_info["pr_number"],
        ticket_id=ticket_id,
        branch=sanitize_filename(pr_data["source_branch"]),
    )

    # Remove existing extension if present and add the correct one
    base_name = Path(base_filename).stem
    extension_map = {"md": ".md", "txt": ".txt", "html": ".html"}
    extension = extension_map.get(output_format.lower(), ".md")
    filename = f"{base_name}{extension}"

    # Convert content based on format
    if output_format.lower() == "html":
        title = f"PR Review: {ticket_id} - {pr_data['title']}"
        content = convert_to_html(review, title)
    else:
        content = review

    output_path = output_dir / filename
    output_path.write_text(content)

    return output_path


# GitHub-style CSS for HTML output
GITHUB_CSS = """
<style>
:root {
    --color-fg-default: #1f2328;
    --color-bg-default: #ffffff;
    --color-border-default: #d0d7de;
    --color-bg-muted: #f6f8fa;
    --color-fg-muted: #656d76;
}
@media (prefers-color-scheme: dark) {
    :root {
        --color-fg-default: #e6edf3;
        --color-bg-default: #0d1117;
        --color-border-default: #30363d;
        --color-bg-muted: #161b22;
        --color-fg-muted: #8d96a0;
    }
}
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
    font-size: 16px;
    line-height: 1.6;
    color: var(--color-fg-default);
    background-color: var(--color-bg-default);
    max-width: 980px;
    margin: 0 auto;
    padding: 32px;
}
h1, h2, h3, h4, h5, h6 {
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
    border-bottom: 1px solid var(--color-border-default);
    padding-bottom: 0.3em;
}
h1 { font-size: 2em; }
h2 { font-size: 1.5em; }
h3 { font-size: 1.25em; border-bottom: none; }
h4 { font-size: 1em; border-bottom: none; }
code {
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    font-size: 85%;
    background-color: var(--color-bg-muted);
    padding: 0.2em 0.4em;
    border-radius: 6px;
}
pre {
    background-color: var(--color-bg-muted);
    border-radius: 6px;
    padding: 16px;
    overflow: auto;
    font-size: 85%;
    line-height: 1.45;
}
pre code {
    background-color: transparent;
    padding: 0;
    border-radius: 0;
}
blockquote {
    border-left: 4px solid var(--color-border-default);
    margin: 0;
    padding: 0 16px;
    color: var(--color-fg-muted);
}
hr {
    border: 0;
    border-top: 1px solid var(--color-border-default);
    margin: 24px 0;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
}
th, td {
    border: 1px solid var(--color-border-default);
    padding: 6px 13px;
}
th {
    background-color: var(--color-bg-muted);
    font-weight: 600;
}
ul, ol {
    padding-left: 2em;
    margin: 16px 0;
}
li + li {
    margin-top: 4px;
}
a {
    color: #0969da;
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
}
strong {
    font-weight: 600;
}
/* Syntax highlighting - Pygments compatible */
.highlight { background: var(--color-bg-muted); }
.highlight .c { color: #6e7781; } /* Comment */
.highlight .k { color: #cf222e; } /* Keyword */
.highlight .s { color: #0a3069; } /* String */
.highlight .n { color: var(--color-fg-default); } /* Name */
.highlight .o { color: var(--color-fg-default); } /* Operator */
.highlight .p { color: var(--color-fg-default); } /* Punctuation */
.highlight .nf { color: #8250df; } /* Function */
.highlight .nc { color: #953800; } /* Class */
/* Severity badges */
.severity-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    margin-right: 8px;
}
.severity-critical {
    background-color: #d73a49;
    color: #ffffff;
}
.severity-high {
    background-color: #e36209;
    color: #ffffff;
}
.severity-medium {
    background-color: #dbab09;
    color: #1f2328;
}
.severity-low {
    background-color: #28a745;
    color: #ffffff;
}
@media (prefers-color-scheme: dark) {
    .severity-critical { background-color: #f85149; }
    .severity-high { background-color: #db6d28; }
    .severity-medium { background-color: #d29922; color: #ffffff; }
    .severity-low { background-color: #3fb950; }
}
</style>
"""


def convert_to_html(markdown_content: str, title: str = "PR Review") -> str:
    """Convert markdown content to styled HTML with GitHub-like styling."""
    try:
        import markdown
        from markdown.extensions.codehilite import CodeHiliteExtension
        from markdown.extensions.fenced_code import FencedCodeExtension
        from markdown.extensions.tables import TableExtension
    except ImportError:
        print("Warning: markdown package not installed. Install with: pip install markdown pygments")
        # Fallback: wrap in basic HTML
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
</head>
<body>
<pre>{markdown_content}</pre>
</body>
</html>"""

    # Convert markdown to HTML with extensions
    md = markdown.Markdown(
        extensions=[
            FencedCodeExtension(),
            CodeHiliteExtension(css_class="highlight", guess_lang=True),
            TableExtension(),
            "nl2br",
        ]
    )
    html_body = md.convert(markdown_content)

    # Post-process: Convert severity labels to styled badges
    # Matches patterns like: <h3>🔴 Critical: Issue Title</h3>
    severity_patterns = [
        # Unicode emoji format
        (r'(<h3>)\s*🔴\s*Critical:', r'\1<span class="severity-badge severity-critical">Critical</span>'),
        (r'(<h3>)\s*🟠\s*High:', r'\1<span class="severity-badge severity-high">High</span>'),
        (r'(<h3>)\s*🟡\s*Medium:', r'\1<span class="severity-badge severity-medium">Medium</span>'),
        (r'(<h3>)\s*🟢\s*Low:', r'\1<span class="severity-badge severity-low">Low</span>'),
        # Markdown emoji shortcode format (AI sometimes outputs these)
        (r'(<h3>)\s*:red_circle:\s*Critical:', r'\1<span class="severity-badge severity-critical">Critical</span>'),
        (r'(<h3>)\s*:orange_circle:\s*High:', r'\1<span class="severity-badge severity-high">High</span>'),
        (r'(<h3>)\s*:yellow_circle:\s*Medium:', r'\1<span class="severity-badge severity-medium">Medium</span>'),
        (r'(<h3>)\s*:green_circle:\s*Low:', r'\1<span class="severity-badge severity-low">Low</span>'),
        # Fallback without emoji
        (r'(<h3>)\s*Critical:', r'\1<span class="severity-badge severity-critical">Critical</span>'),
        (r'(<h3>)\s*High:', r'\1<span class="severity-badge severity-high">High</span>'),
        (r'(<h3>)\s*Medium:', r'\1<span class="severity-badge severity-medium">Medium</span>'),
        (r'(<h3>)\s*Low:', r'\1<span class="severity-badge severity-low">Low</span>'),
    ]
    for pattern, replacement in severity_patterns:
        html_body = re.sub(pattern, replacement, html_body, flags=re.IGNORECASE)

    # Post-process: Convert plain URLs to clickable links
    # Matches URLs not already inside href="" or wrapped in <a> tags
    url_pattern = r'(?<!href=["\'])(?<!</a>)(https?://[^\s<>"\']+)'
    html_body = re.sub(url_pattern, r'<a href="\1">\1</a>', html_body)

    # Wrap in full HTML document with styling
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {GITHUB_CSS}
</head>
<body>
{html_body}
</body>
</html>"""


def auto_open_file(file_path: Path) -> bool:
    """Open file in the default application. Returns True if successful."""
    try:
        file_url = file_path.as_uri()

        # For HTML files, use webbrowser module
        if file_path.suffix.lower() == ".html":
            webbrowser.open(file_url)
            return True

        # For other files, use platform-specific commands
        system = platform.system()
        if system == "Darwin":  # macOS
            subprocess.run(["open", str(file_path)], check=True)
        elif system == "Windows":
            os.startfile(str(file_path))
        else:  # Linux and others
            subprocess.run(["xdg-open", str(file_path)], check=True)
        return True
    except Exception as e:
        print(f"Could not open file automatically: {e}")
        return False



GITHUB_REPO = "aaronmedina-dev/WhatThePatch"
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"

# Files that can be updated from GitHub (legacy fallback if manifest.json not available)
UPDATABLE_FILES = [
    "whatthepatch.py",
    "cli_utils.py",
    "banner.py",
    "prompt.md",
    "requirements.txt",
    "manifest.json",
    "setup.py",
    "config.example.yaml",
    "engines/__init__.py",
    "engines/base.py",
    "engines/claude_api.py",
    "engines/claude_cli.py",
    "engines/openai_api.py",
    "engines/openai_codex_cli.py",
    "engines/gemini_api.py",
    "engines/gemini_cli.py",
    "engines/ollama_api.py",
    "docs/configuration.md",
    "docs/engines.md",
    "docs/external-context.md",
    "docs/prompts.md",
    "docs/troubleshooting.md",
    "prompt-templates/backend-prompt.md",
    "prompt-templates/devops-prompt.md",
    "prompt-templates/frontend-prompt.md",
    "prompt-templates/microservices-prompt.md",
]


def _get_git_root(path: Path) -> Path | None:
    """Get the root directory of the git repository containing path."""
    current = path
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def _install_requirements(requirements_path: Path) -> bool:
    """Install requirements from requirements.txt. Returns True on success."""
    import subprocess

    if not requirements_path.exists():
        console.print(f"[dim]No requirements.txt found at {requirements_path}[/dim]")
        return True  # Not an error if file doesn't exist

    console.print()
    console.print("[bold]Checking dependencies...[/bold]")

    with get_progress_spinner() as progress:
        progress.add_task("Installing requirements...", total=None)
        try:
            # Use pip to install requirements
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_path), "-q"],
                capture_output=True,
                text=True,
                timeout=120
            )
        except subprocess.TimeoutExpired:
            print_warning("pip install timed out - you may need to run manually:")
            console.print(f"  [cyan]pip install -r {requirements_path}[/cyan]")
            return False
        except FileNotFoundError:
            print_warning("pip not found - install dependencies manually:")
            console.print(f"  [cyan]pip install -r {requirements_path}[/cyan]")
            return False
        except Exception as e:
            print_warning(f"Failed to install requirements: {e}")
            return False

    if result.returncode == 0:
        console.print("[green]Dependencies up to date[/green]")
        return True
    else:
        print_warning("Some dependencies may have failed to install")
        if result.stderr:
            console.print(f"[dim]{result.stderr.strip()}[/dim]")
        console.print()
        console.print("Run manually if needed:")
        console.print(f"  [cyan]pip install -r {requirements_path}[/cyan]")
        return False


def _update_via_git(repo_root: Path) -> bool:
    """Update using git pull. Returns True on success."""
    import subprocess

    info_table = create_key_value_table()
    info_table.add_row("Repository", str(repo_root))
    info_table.add_row("Source", f"github.com/{GITHUB_REPO}")
    console.print(info_table)
    console.print()

    # Check for uncommitted changes
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.stdout.strip():
            print_warning("You have uncommitted changes. Consider committing or stashing them before updating.")
            console.print()
    except Exception:
        pass

    # Run git pull with spinner
    with get_progress_spinner() as progress:
        progress.add_task("Running git pull...", total=None)
        try:
            result = subprocess.run(
                ["git", "pull"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=60
            )
        except subprocess.TimeoutExpired:
            print_error("git pull timed out")
            return False
        except FileNotFoundError:
            print_error("git command not found")
            return False
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            return False

    if result.returncode == 0:
        output = result.stdout.strip()
        if output:
            console.print(f"[dim]{output}[/dim]")
            console.print()
        print_success("Update complete!")
        return True
    else:
        print_error("git pull failed", [result.stderr.strip()])
        return False


def _fetch_manifest() -> dict | None:
    """Fetch manifest.json from GitHub. Returns parsed manifest or None if unavailable."""
    import json

    manifest_url = f"{GITHUB_RAW_BASE}/manifest.json"
    try:
        response = requests.get(manifest_url, timeout=30)
        if response.status_code == 200:
            return json.loads(response.text)
    except Exception:
        pass
    return None


def _get_files_from_manifest(manifest: dict) -> list[str]:
    """Extract file paths from manifest."""
    files = []
    for file_entry in manifest.get("files", []):
        if isinstance(file_entry, dict):
            files.append(file_entry["path"])
        else:
            files.append(file_entry)
    return files


def _update_via_download(target_dir: Path) -> bool:
    """Update by downloading files from GitHub. Returns True on success."""
    info_table = create_key_value_table()
    info_table.add_row("Target", str(target_dir))
    info_table.add_row("Source", f"github.com/{GITHUB_REPO}")
    console.print(info_table)
    console.print()

    # Try to fetch manifest for file list, fall back to legacy list
    manifest = _fetch_manifest()
    if manifest:
        files_to_update = _get_files_from_manifest(manifest)
        manifest_version = manifest.get("version", "unknown")
        console.print(f"[dim]Using manifest v{manifest_version} ({len(files_to_update)} files)[/dim]")
    else:
        files_to_update = UPDATABLE_FILES
        console.print(f"[dim]Using legacy file list ({len(files_to_update)} files)[/dim]")
    console.print()

    # Ensure required directories exist
    for directory in ["engines", "docs", "prompt-templates"]:
        dir_path = target_dir / directory
        dir_path.mkdir(parents=True, exist_ok=True)

    updated = []
    failed = []
    skipped = []

    with get_progress_spinner() as progress:
        task = progress.add_task("Downloading files...", total=None)

        for filename in files_to_update:
            url = f"{GITHUB_RAW_BASE}/{filename}"
            dest = target_dir / filename

            # Ensure parent directory exists for nested files
            dest.parent.mkdir(parents=True, exist_ok=True)

            progress.update(task, description=f"Downloading {filename}...")
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    dest.write_text(response.text)
                    updated.append(filename)
                elif response.status_code == 404:
                    # File doesn't exist in repo (may be optional)
                    skipped.append((filename, "not found in repo"))
                else:
                    failed.append((filename, f"HTTP {response.status_code}"))
            except Exception as e:
                failed.append((filename, str(e)))

    # Show results
    if updated:
        console.print(f"[green]Updated:[/green] {len(updated)} files")
    if skipped:
        console.print(f"[yellow]Skipped:[/yellow] {len(skipped)} files (not in repo)")
    if failed:
        console.print(f"[red]Failed:[/red] {len(failed)} files")
        for filename, error in failed:
            console.print(f"  [dim]{filename}:[/dim] [red]{error}[/red]")

    console.print()

    # Consider success if we updated files and only had skips (not hard failures)
    if updated and not failed:
        print_success("Update complete!", {"Files updated": str(len(updated))})
        return True
    elif failed:
        print_error("Some files failed to update", [
            f"Clone manually: git clone https://github.com/{GITHUB_REPO}",
            "Run setup.py from the cloned repo"
        ])
        return False
    return False


def run_update():
    """Update WhatThePatch from GitHub.

    Handles three scenarios:
    1. Running as CLI (wtp command) from ~/.whatthepatch - download from GitHub
    2. Running as .py script from a git repo - use git pull
    3. Running as .py script not in a git repo - download from GitHub to script location
    """
    console.print()
    console.print("[bold]Updating WhatThePatch[/bold]")
    console.print()

    # Determine the script's actual location
    script_path = Path(__file__).resolve()
    script_dir = script_path.parent

    # Check if running from installed location (~/.whatthepatch)
    is_installed = script_dir == INSTALL_DIR

    update_success = False
    requirements_path = None

    if is_installed:
        # Scenario 1: Running as CLI command from install directory
        console.print(f"[dim]Mode:[/dim] Installed CLI (wtp command)")
        console.print()
        update_success = _update_via_download(INSTALL_DIR)
        requirements_path = INSTALL_DIR / "requirements.txt"
    else:
        # Running directly as .py script
        git_root = _get_git_root(script_dir)

        if git_root:
            # Scenario 2: Running from a git repository
            console.print(f"[dim]Mode:[/dim] Git repository")
            console.print()
            update_success = _update_via_git(git_root)
            requirements_path = git_root / "requirements.txt"
        else:
            # Scenario 3: Running as .py script but not in a git repo
            console.print(f"[dim]Mode:[/dim] Standalone script")
            console.print()
            update_success = _update_via_download(script_dir)
            requirements_path = script_dir / "requirements.txt"

    # Install/update dependencies if update was successful
    if update_success and requirements_path:
        _install_requirements(requirements_path)

    # Clear update cache so next check fetches fresh data
    if UPDATE_CACHE_FILE.exists():
        try:
            UPDATE_CACHE_FILE.unlink()
        except IOError:
            pass


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
