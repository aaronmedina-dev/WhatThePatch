"""
URL and Context Handling for WhatThePatch.

This module handles:
- URL parsing and fetching (GitHub, Bitbucket, generic URLs)
- Local file/directory reading
- URL caching
- HTML to Markdown conversion
- Context formatting for AI prompts
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import html2text
import requests
import yaml


# Version for User-Agent header (imported from main module when needed)
# We'll accept this as a parameter to avoid circular imports
__version__ = "1.3.0"  # Updated during release

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
