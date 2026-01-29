"""
WhatThePatch - Update System

This module handles self-update functionality:
- Version checking and update notifications
- Git-based and download-based updates
- Manifest-based file management
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

from cli_utils import (
    console,
    print_error,
    print_warning,
    print_success,
    print_info,
    get_progress_spinner,
    create_key_value_table,
)

# Import version from whatthepatch
def _get_version() -> str:
    """Get version - imports from whatthepatch to avoid circular import."""
    from whatthepatch import __version__
    return __version__


# Install directory for all WhatThePatch files
INSTALL_DIR = Path.home() / ".whatthepatch"


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
            current = parse_version(_get_version())
            latest = parse_version(cached_latest)
            if latest > current:
                return (True, _get_version(), cached_latest)
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
            current = parse_version(_get_version())
            latest = parse_version(latest_version)

            if latest > current:
                return (True, _get_version(), latest_version)
            return (False, _get_version(), latest_version)

        elif response.status_code == 404:
            # No releases yet - update cache to avoid repeated checks
            cache["last_check"] = current_time
            cache["latest_version"] = _get_version()
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


