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


# Install directory for all WhatThePatch files
INSTALL_DIR = Path.home() / ".whatthepatch"

# Context reading configuration
CONTEXT_SIZE_WARNING_THRESHOLD = 100_000  # ~100KB

# Directories to auto-exclude when reading context
EXCLUDED_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv',
    'vendor', 'dist', 'build', '.next', '.nuxt', 'coverage',
    '.pytest_cache', '.mypy_cache', '.tox', 'egg-info',
    '.idea', '.vscode', '.DS_Store',
}

# Binary/non-text extensions to skip
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp',
    '.woff', '.woff2', '.ttf', '.eot', '.otf',
    '.zip', '.tar', '.gz', '.rar', '.7z', '.bz2',
    '.exe', '.dll', '.so', '.dylib', '.bin',
    '.pyc', '.pyo', '.class', '.o', '.obj',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.mp3', '.mp4', '.wav', '.avi', '.mov', '.mkv',
    '.sqlite', '.db', '.lock',
}

# URL cache configuration
URL_CACHE_DIR = INSTALL_DIR / "url_cache"
URL_CACHE_TTL = 3600  # 1 hour in seconds


def is_url(path: str) -> bool:
    """Check if a path is a URL."""
    return path.startswith(('http://', 'https://'))


def convert_github_blob_to_raw(url: str) -> str:
    """Convert GitHub blob URL to raw content URL.

    Example:
        https://github.com/owner/repo/blob/branch/path/file.py
        -> https://raw.githubusercontent.com/owner/repo/branch/path/file.py
    """
    pattern = r'https://github\.com/([^/]+)/([^/]+)/blob/(.+)'
    match = re.match(pattern, url)
    if match:
        owner, repo, path = match.groups()
        return f'https://raw.githubusercontent.com/{owner}/{repo}/{path}'
    return url


def parse_github_url(url: str) -> tuple[str, str, str, str] | None:
    """Parse a GitHub URL to extract owner, repo, ref, and path.

    Supports:
        https://github.com/owner/repo/blob/branch/path/to/file.py
        https://raw.githubusercontent.com/owner/repo/branch/path/to/file.py

    Returns:
        tuple: (owner, repo, ref, path) or None if not a GitHub URL
    """
    # GitHub blob URL pattern
    blob_pattern = r'https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)'
    match = re.match(blob_pattern, url)
    if match:
        return match.groups()

    # Raw GitHub URL pattern
    raw_pattern = r'https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)'
    match = re.match(raw_pattern, url)
    if match:
        return match.groups()

    return None


def fetch_github_file_content(owner: str, repo: str, ref: str, path: str, token: str | None = None) -> str:
    """Fetch file content from GitHub using the Contents API.

    This supports both public and private repos (with token).

    Args:
        owner: Repository owner
        repo: Repository name
        ref: Branch, tag, or commit SHA
        path: File path within the repository
        token: GitHub personal access token (optional, required for private repos)

    Returns:
        File content as string

    Raises:
        requests.exceptions.HTTPError: On API errors
    """
    import base64

    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': f'WhatThePatch/{__version__}'
    }
    if token:
        headers['Authorization'] = f'token {token}'

    response = requests.get(api_url, headers=headers, params={'ref': ref}, timeout=30)
    response.raise_for_status()

    data = response.json()

    # Handle file content (base64 encoded)
    if data.get('type') == 'file' and 'content' in data:
        content = base64.b64decode(data['content']).decode('utf-8')
        return content

    # If it's a directory or something else, raise an error
    raise ValueError(f"URL points to a {data.get('type', 'unknown')}, not a file")


def parse_bitbucket_url(url: str) -> tuple[str, str, str, str] | None:
    """Parse a Bitbucket URL to extract workspace, repo, ref, and path.

    Supports:
        https://bitbucket.org/workspace/repo/src/branch/path/to/file.py

    Returns:
        tuple: (workspace, repo, ref, path) or None if not a Bitbucket URL
    """
    # Bitbucket src URL pattern
    pattern = r'https://bitbucket\.org/([^/]+)/([^/]+)/src/([^/]+)/(.+)'
    match = re.match(pattern, url)
    if match:
        return match.groups()
    return None


def fetch_bitbucket_file_content(workspace: str, repo: str, ref: str, path: str,
                                  username: str | None = None, app_password: str | None = None) -> str:
    """Fetch file content from Bitbucket using the API.

    This supports both public and private repos (with credentials).

    Args:
        workspace: Bitbucket workspace
        repo: Repository slug
        ref: Branch, tag, or commit SHA
        path: File path within the repository
        username: Bitbucket username (optional, required for private repos)
        app_password: Bitbucket app password (optional, required for private repos)

    Returns:
        File content as string

    Raises:
        requests.exceptions.HTTPError: On API errors
    """
    api_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo}/src/{ref}/{path}"
    headers = {
        'User-Agent': f'WhatThePatch/{__version__}'
    }

    auth = None
    if username and app_password:
        auth = (username, app_password)

    response = requests.get(api_url, headers=headers, auth=auth, timeout=30)
    response.raise_for_status()

    # Bitbucket returns raw file content directly
    return response.text


def is_html_content(content_type: str | None, content: str) -> bool:
    """Check if content is HTML based on Content-Type header or content inspection."""
    if content_type and 'text/html' in content_type.lower():
        return True
    # Fallback: check if content starts with HTML-like tags
    stripped = content.strip()[:500].lower()
    return stripped.startswith('<!doctype html') or stripped.startswith('<html')


def html_to_markdown(html_content: str) -> str:
    """Convert HTML to Markdown using html2text."""
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.ignore_emphasis = False
    h.body_width = 0  # Don't wrap lines
    h.unicode_snob = True
    return h.handle(html_content)


def get_url_cache_path(url: str) -> Path:
    """Get cache file path for a URL."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    URL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return URL_CACHE_DIR / f"{url_hash}.json"


def get_cached_content(url: str, ttl: int = URL_CACHE_TTL) -> tuple[str, str, int] | None:
    """Get cached content if valid. Returns (content, display_name, size) or None."""
    cache_path = get_url_cache_path(url)
    if not cache_path.exists():
        return None

    try:
        with open(cache_path) as f:
            data = json.load(f)

        if time.time() - data["fetched_at"] > ttl:
            return None  # Expired

        return (data["content"], data["display_name"], len(data["content"].encode()))
    except (json.JSONDecodeError, KeyError):
        return None


def save_to_cache(url: str, content: str, display_name: str, content_type: str):
    """Save fetched content to cache."""
    cache_path = get_url_cache_path(url)
    data = {
        "url": url,
        "content": content,
        "fetched_at": time.time(),
        "content_type": content_type,
        "display_name": display_name
    }
    with open(cache_path, "w") as f:
        json.dump(data, f)


def get_github_token() -> str | None:
    """Get GitHub token from config if available."""
    config_path = INSTALL_DIR / "config.yaml"
    if not config_path.exists():
        # Try local config
        config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        return None

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        token = config.get("tokens", {}).get("github", "")
        # Check if it's a real token (not a placeholder)
        if token and not token.startswith("ghp_your"):
            return token
    except Exception:
        pass
    return None


def get_bitbucket_credentials() -> tuple[str | None, str | None]:
    """Get Bitbucket credentials from config if available.

    Returns:
        tuple: (username, app_password) or (None, None) if not configured
    """
    config_path = INSTALL_DIR / "config.yaml"
    if not config_path.exists():
        # Try local config
        config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        return None, None

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        tokens = config.get("tokens", {})
        username = tokens.get("bitbucket_username", "")
        app_password = tokens.get("bitbucket_app_password", "")
        # Check if they're real credentials (not placeholders)
        if username and app_password and not username.startswith("your_"):
            return username, app_password
    except Exception:
        pass
    return None, None


def fetch_url_content(url: str, use_cache: bool = True) -> tuple[str, str, int]:
    """Fetch content from a URL with caching support.

    For GitHub/Bitbucket URLs, uses their APIs with authentication if configured.
    This allows fetching files from private repositories.

    Args:
        url: The URL to fetch
        use_cache: Whether to use caching (default True)

    Returns:
        tuple: (content, display_name, size_bytes)

    Raises:
        requests.exceptions.RequestException: On network errors, HTTP errors, etc.
    """
    # Check cache first
    if use_cache:
        cached = get_cached_content(url)
        if cached:
            return cached

    content = None
    content_type = ''
    display_name = ''

    # Check if this is a GitHub URL
    github_parts = parse_github_url(url)
    if github_parts:
        owner, repo, ref, path = github_parts
        display_name = path.split('/')[-1]

        # Try to get GitHub token for authenticated access
        github_token = get_github_token()

        try:
            # Use GitHub API (supports private repos with token)
            content = fetch_github_file_content(owner, repo, ref, path, github_token)
            content_type = 'text/plain'  # GitHub API returns raw content
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404 and not github_token:
                # Re-raise with helpful message about authentication
                raise requests.exceptions.HTTPError(
                    f"404: File not found. If this is a private repo, ensure your GitHub token is configured.",
                    response=e.response
                )
            raise

    # Check if this is a Bitbucket URL
    elif (bitbucket_parts := parse_bitbucket_url(url)):
        workspace, repo, ref, path = bitbucket_parts
        display_name = path.split('/')[-1]

        # Try to get Bitbucket credentials for authenticated access
        bb_username, bb_password = get_bitbucket_credentials()

        try:
            # Use Bitbucket API (supports private repos with credentials)
            content = fetch_bitbucket_file_content(workspace, repo, ref, path, bb_username, bb_password)
            content_type = 'text/plain'  # Bitbucket API returns raw content
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404 and not bb_username:
                # Re-raise with helpful message about authentication
                raise requests.exceptions.HTTPError(
                    f"404: File not found. If this is a private repo, ensure your Bitbucket credentials are configured.",
                    response=e.response
                )
            raise

    else:
        # Non-GitHub/Bitbucket URL - use direct HTTP fetch
        fetch_url = url

        # Parse URL for display name
        parsed = urlparse(fetch_url)
        path_parts = parsed.path.strip('/').split('/')
        display_name = path_parts[-1] if path_parts else parsed.netloc

        # Fetch with timeout
        response = requests.get(fetch_url, timeout=30, headers={
            'User-Agent': f'WhatThePatch/{__version__}'
        })
        response.raise_for_status()

        content = response.text
        content_type = response.headers.get('Content-Type', '')

    # Convert HTML to Markdown if needed
    if is_html_content(content_type, content):
        content = html_to_markdown(content)
        display_name = f"{display_name} (HTML->MD)"

    size = len(content.encode('utf-8'))

    # Save to cache
    if use_cache:
        save_to_cache(url, content, display_name, content_type)

    return content, display_name, size


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


def is_text_file(filepath: Path) -> bool:
    """Check if file is likely a text file based on extension."""
    return filepath.suffix.lower() not in BINARY_EXTENSIONS


def should_exclude_dir(dirpath: Path) -> bool:
    """Check if directory should be excluded from context reading."""
    return dirpath.name in EXCLUDED_DIRS


def read_context_paths(paths: list[str]) -> tuple[str, int, int, int]:
    """
    Read content from files, directories, or URLs.

    Args:
        paths: List of file paths, directory paths, or URLs to read

    Returns:
        Tuple of (formatted_content, total_size_bytes, local_count, url_count)
    """
    files_content: dict[str, str] = {}
    url_content: list[tuple[str, str]] = []  # List of (display_name, content)
    total_size = 0
    errors = []
    local_count = 0
    url_count = 0

    for path_str in paths:
        if is_url(path_str):
            # Handle URL
            try:
                content, display_name, size = fetch_url_content(path_str)
                url_content.append((display_name, content))
                total_size += size
                url_count += 1
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    errors.append(f"URL not found: {path_str}")
                elif e.response.status_code == 403:
                    errors.append(f"Access denied: {path_str} (may require authentication)")
                else:
                    errors.append(f"HTTP {e.response.status_code}: {path_str}")
            except requests.exceptions.Timeout:
                errors.append(f"Timeout fetching URL: {path_str}")
            except requests.exceptions.RequestException as e:
                errors.append(f"Failed to fetch URL: {path_str} ({e})")
        else:
            # Handle local path
            path = Path(path_str).expanduser().resolve()

            if not path.exists():
                errors.append(f"Path not found: {path_str}")
                continue

            if path.is_file():
                # Single file
                if is_text_file(path):
                    try:
                        content = path.read_text(errors='replace')
                        files_content[str(path)] = content
                        total_size += len(content.encode('utf-8'))
                        local_count += 1
                    except Exception as e:
                        errors.append(f"Could not read {path}: {e}")
                else:
                    errors.append(f"Skipped binary file: {path}")

            elif path.is_dir():
                # Directory - read recursively
                for root, dirs, files in os.walk(path):
                    root_path = Path(root)

                    # Filter out excluded directories (modifies dirs in-place)
                    dirs[:] = [d for d in dirs if not should_exclude_dir(root_path / d)]

                    for filename in files:
                        filepath = root_path / filename
                        if is_text_file(filepath):
                            try:
                                content = filepath.read_text(errors='replace')
                                # Use relative path from the provided context root
                                relative_path = filepath.relative_to(path.parent)
                                files_content[str(relative_path)] = content
                                total_size += len(content.encode('utf-8'))
                                local_count += 1
                            except Exception:
                                # Silently skip files that can't be read
                                pass

    # Report errors
    if errors:
        print("\nContext reading warnings:")
        for error in errors:
            print(f"  - {error}")
        print()

    if not files_content and not url_content:
        return "No readable content found in the provided context paths.", 0, 0, 0

    return format_context_content(files_content, url_content), total_size, local_count, url_count


def format_context_content(files: dict[str, str], urls: list[tuple[str, str]] | None = None) -> str:
    """Format file and URL contents with clear separators for the AI prompt.

    Args:
        files: Dict mapping filepath to content for local files
        urls: List of (display_name, content) tuples for URL-fetched content
    """
    lines = ["The following external files have been provided as additional context:\n"]

    # Format local files
    for filepath, content in sorted(files.items()):
        # Detect language from extension for code fence
        ext = Path(filepath).suffix.lower()
        lang_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.tsx': 'tsx', '.jsx': 'jsx', '.java': 'java', '.go': 'go',
            '.rs': 'rust', '.rb': 'ruby', '.php': 'php', '.cs': 'csharp',
            '.cpp': 'cpp', '.c': 'c', '.h': 'c', '.hpp': 'cpp',
            '.swift': 'swift', '.kt': 'kotlin', '.scala': 'scala',
            '.sh': 'bash', '.bash': 'bash', '.zsh': 'zsh',
            '.yaml': 'yaml', '.yml': 'yaml', '.json': 'json',
            '.xml': 'xml', '.html': 'html', '.css': 'css',
            '.sql': 'sql', '.md': 'markdown', '.graphql': 'graphql',
        }
        lang = lang_map.get(ext, '')

        lines.append(f"### File: {filepath}")
        lines.append(f"```{lang}")
        lines.append(content.rstrip())
        lines.append("```")
        lines.append("")

    # Format URL content
    if urls:
        for display_name, content in urls:
            # Try to detect language from display name extension
            ext = Path(display_name.split(' ')[0]).suffix.lower()  # Handle "(HTML->MD)" suffix
            lang_map = {
                '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                '.tsx': 'tsx', '.jsx': 'jsx', '.java': 'java', '.go': 'go',
                '.rs': 'rust', '.rb': 'ruby', '.php': 'php', '.cs': 'csharp',
                '.cpp': 'cpp', '.c': 'c', '.h': 'c', '.hpp': 'cpp',
                '.swift': 'swift', '.kt': 'kotlin', '.scala': 'scala',
                '.sh': 'bash', '.bash': 'bash', '.zsh': 'zsh',
                '.yaml': 'yaml', '.yml': 'yaml', '.json': 'json',
                '.xml': 'xml', '.html': 'markdown', '.css': 'css',
                '.sql': 'sql', '.md': 'markdown', '.graphql': 'graphql',
            }
            # HTML->MD content should be rendered as markdown
            if '(HTML->MD)' in display_name:
                lang = 'markdown'
            else:
                lang = lang_map.get(ext, '')

            lines.append(f"### URL: {display_name}")
            lines.append(f"```{lang}")
            lines.append(content.rstrip())
            lines.append("```")
            lines.append("")

    return "\n".join(lines)


def check_context_size(size_bytes: int) -> bool:
    """
    Check if context size exceeds threshold.
    If so, warn user and ask for confirmation.

    Args:
        size_bytes: Total size of context in bytes

    Returns:
        True if should proceed, False to abort.
    """
    if size_bytes <= CONTEXT_SIZE_WARNING_THRESHOLD:
        return True

    size_kb = size_bytes / 1024
    threshold_kb = CONTEXT_SIZE_WARNING_THRESHOLD / 1024

    print(f"\nWarning: External context is large ({size_kb:.1f}KB)")
    print(f"This exceeds the recommended threshold of {threshold_kb:.0f}KB")
    print("Large context may increase API costs and processing time.\n")

    try:
        response = input("Continue anyway? (y/n): ").strip().lower()
        return response == 'y'
    except KeyboardInterrupt:
        print("\n")
        return False


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


def parse_pr_url(url: str) -> dict:
    """Parse PR URL and extract platform, owner, repo, and PR number."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    path_parts = parsed.path.strip("/").split("/")

    if "github.com" in hostname:
        # GitHub: https://github.com/owner/repo/pull/123
        if len(path_parts) >= 4 and path_parts[2] == "pull":
            return {
                "platform": "github",
                "owner": path_parts[0],
                "repo": path_parts[1],
                "pr_number": path_parts[3],
            }
    elif "bitbucket.org" in hostname:
        # Bitbucket: https://bitbucket.org/workspace/repo/pull-requests/123
        if len(path_parts) >= 4 and path_parts[2] == "pull-requests":
            return {
                "platform": "bitbucket",
                "owner": path_parts[0],
                "repo": path_parts[1],
                "pr_number": path_parts[3],
            }

    from cli_utils import print_cli_error
    print_cli_error(
        f"Could not parse PR URL: [yellow]{url}[/yellow]",
        hints=[
            "Supported formats:",
            "  GitHub:    https://github.com/owner/repo/pull/123",
            "  Bitbucket: https://bitbucket.org/workspace/repo/pull-requests/123",
        ]
    )
    sys.exit(1)


def fetch_github_pr(owner: str, repo: str, pr_number: str, token: str) -> dict:
    """Fetch PR details and diff from GitHub API."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Fetch PR metadata
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    response = requests.get(pr_url, headers=headers)

    if response.status_code != 200:
        print(f"Error fetching PR from GitHub: {response.status_code}")
        print(response.text)
        sys.exit(1)

    pr_data = response.json()

    # Fetch diff
    headers["Accept"] = "application/vnd.github.v3.diff"
    diff_response = requests.get(pr_url, headers=headers)

    if diff_response.status_code != 200:
        print(f"Error fetching diff from GitHub: {diff_response.status_code}")
        sys.exit(1)

    return {
        "title": pr_data["title"],
        "description": pr_data.get("body") or "(No description provided)",
        "source_branch": pr_data["head"]["ref"],
        "target_branch": pr_data["base"]["ref"],
        "diff": diff_response.text,
        "author": pr_data["user"]["login"],
    }


def fetch_bitbucket_pr(
    workspace: str, repo: str, pr_number: str, username: str, app_password: str
) -> dict:
    """Fetch PR details and diff from Bitbucket API."""
    auth = (username, app_password)

    # Fetch PR metadata
    pr_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo}/pullrequests/{pr_number}"
    response = requests.get(pr_url, auth=auth)

    if response.status_code != 200:
        print(f"Error fetching PR from Bitbucket: {response.status_code}")
        print(response.text)
        sys.exit(1)

    pr_data = response.json()

    # Fetch diff
    diff_url = f"{pr_url}/diff"
    diff_response = requests.get(diff_url, auth=auth)

    if diff_response.status_code != 200:
        print(f"Error fetching diff from Bitbucket: {diff_response.status_code}")
        sys.exit(1)

    return {
        "title": pr_data["title"],
        "description": pr_data.get("description") or "(No description provided)",
        "source_branch": pr_data["source"]["branch"]["name"],
        "target_branch": pr_data["destination"]["branch"]["name"],
        "diff": diff_response.text,
        "author": pr_data["author"]["display_name"],
    }


def extract_ticket_id(branch_name: str, pattern: str, fallback: str) -> str:
    """Extract ticket ID from branch name using regex pattern."""
    match = re.search(pattern, branch_name)
    if match:
        return match.group(1)
    return fallback


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use in filenames."""
    return re.sub(r"[^\w\-_]", "-", name)


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


GITHUB_REPO = "aaronmedina-dev/WhatThePatch"
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"

# Files that can be updated from GitHub
UPDATABLE_FILES = [
    "whatthepatch.py",
    "cli_utils.py",
    "banner.py",
    "prompt.md",
    "requirements.txt",
    "engines/__init__.py",
    "engines/base.py",
    "engines/claude_api.py",
    "engines/claude_cli.py",
    "engines/openai_api.py",
    "engines/openai_codex_cli.py",
    "engines/gemini_api.py",
    "engines/gemini_cli.py",
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


def _update_via_download(target_dir: Path) -> bool:
    """Update by downloading files from GitHub. Returns True on success."""
    info_table = create_key_value_table()
    info_table.add_row("Target", str(target_dir))
    info_table.add_row("Source", f"github.com/{GITHUB_REPO}")
    console.print(info_table)
    console.print()

    # Ensure engines directory exists
    engines_dir = target_dir / "engines"
    engines_dir.mkdir(parents=True, exist_ok=True)

    updated = []
    failed = []

    with get_progress_spinner() as progress:
        task = progress.add_task("Downloading files...", total=None)

        for filename in UPDATABLE_FILES:
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
                else:
                    failed.append((filename, f"HTTP {response.status_code}"))
            except Exception as e:
                failed.append((filename, str(e)))

    # Show results
    if updated:
        console.print(f"[green]Updated:[/green] {len(updated)} files")
    if failed:
        console.print(f"[red]Failed:[/red] {len(failed)} files")
        for filename, error in failed:
            console.print(f"  [dim]{filename}:[/dim] [red]{error}[/red]")

    console.print()

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
