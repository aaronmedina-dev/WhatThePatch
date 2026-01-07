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

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml


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


def load_prompt_template() -> str:
    """Load the review prompt template from prompt.md"""
    prompt_path = get_file_path("prompt.md")

    if not prompt_path.exists():
        print(f"Error: prompt.md not found at {prompt_path}")
        print("Please run setup.py to install WhatThePatch.")
        sys.exit(1)

    return prompt_path.read_text()


def load_config() -> dict:
    """Load configuration from config.yaml"""
    config_path = get_file_path("config.yaml")

    if not config_path.exists():
        print(f"Error: config.yaml not found at {config_path}")
        print("Please run setup.py to configure WhatThePatch.")
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

    print(f"Error: Could not parse PR URL: {url}")
    print("Supported formats:")
    print("  GitHub: https://github.com/owner/repo/pull/123")
    print("  Bitbucket: https://bitbucket.org/workspace/repo/pull-requests/123")
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


def generate_review(pr_data: dict, ticket_id: str, config: dict) -> str:
    """Generate PR review using configured engine."""
    try:
        from engines import get_engine, EngineError
    except ImportError as e:
        print(f"Error: Could not load engines module: {e}")
        print("Please run setup.py to install WhatThePatch properly.")
        sys.exit(1)

    engine_name = config.get("engine", "claude-api")
    prompt_template = load_prompt_template()

    try:
        engine = get_engine(engine_name, config)
        return engine.generate_review(pr_data, ticket_id, prompt_template)
    except EngineError as e:
        print(f"Error: {e}")
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
        (r'(<h3>)\s*🔴\s*Critical:', r'\1<span class="severity-badge severity-critical">Critical</span>'),
        (r'(<h3>)\s*🟠\s*High:', r'\1<span class="severity-badge severity-high">High</span>'),
        (r'(<h3>)\s*🟡\s*Medium:', r'\1<span class="severity-badge severity-medium">Medium</span>'),
        (r'(<h3>)\s*🟢\s*Low:', r'\1<span class="severity-badge severity-low">Low</span>'),
        # Also handle without emoji (fallback)
        (r'(<h3>)\s*Critical:', r'\1<span class="severity-badge severity-critical">Critical</span>'),
        (r'(<h3>)\s*High:', r'\1<span class="severity-badge severity-high">High</span>'),
        (r'(<h3>)\s*Medium:', r'\1<span class="severity-badge severity-medium">Medium</span>'),
        (r'(<h3>)\s*Low:', r'\1<span class="severity-badge severity-low">Low</span>'),
    ]
    for pattern, replacement in severity_patterns:
        html_body = re.sub(pattern, replacement, html_body, flags=re.IGNORECASE)

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
    print("Testing configuration...\n")

    config_path = get_file_path("config.yaml")
    if not config_path.exists():
        print(f"Error: config.yaml not found at {config_path}")
        print("Run 'python setup.py' to configure.")
        return False

    config = load_config()
    issues = []  # Track issues for summary

    # Test AI engine
    engine_name = config.get("engine", "claude-api")
    print(f"Engine: {engine_name}")

    try:
        from engines import get_engine, list_engines, EngineError

        if engine_name not in list_engines():
            print(f"  Unknown engine. Available: {', '.join(list_engines())}")
            issues.append(f"Engine '{engine_name}' not found")
        else:
            print(f"\nTesting {engine_name} engine...")
            try:
                engine = get_engine(engine_name, config)

                # Validate configuration
                is_valid, error = engine.validate_config()
                if not is_valid:
                    print(f"  Configuration error: {error}")
                    issues.append(f"Engine ({engine_name}): {error}")
                else:
                    # Test connection
                    success, error = engine.test_connection()
                    if success:
                        print(f"  {engine.name} is working")
                    else:
                        print(f"  {engine.name}: {error}")
                        issues.append(f"Engine ({engine_name}): {error}")
            except EngineError as e:
                print(f"  Engine error: {e}")
                issues.append(f"Engine ({engine_name}): {e}")
    except ImportError as e:
        print(f"  Could not load engines: {e}")
        issues.append(f"Engines module: {e}")

    # Test GitHub token
    github_token = config.get("tokens", {}).get("github", "")
    if github_token:
        print("\nTesting GitHub token...")
        try:
            response = requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {github_token}"},
                timeout=10,
            )
            if response.status_code == 200:
                print("  GitHub token is valid")
            else:
                print("  GitHub token is invalid")
                issues.append("GitHub: Token is invalid or expired")
        except Exception:
            print("  GitHub token test failed")
            issues.append("GitHub: Could not verify token")
    else:
        print("\nGitHub token: Not configured (optional)")

    # Test Bitbucket credentials
    bb_username = config.get("tokens", {}).get("bitbucket_username", "")
    bb_password = config.get("tokens", {}).get("bitbucket_app_password", "")
    if bb_username and bb_password:
        print("\nTesting Bitbucket credentials...")
        try:
            response = requests.get(
                "https://api.bitbucket.org/2.0/user",
                auth=(bb_username, bb_password),
                timeout=10,
            )
            if response.status_code == 200:
                print("  Bitbucket credentials are valid")
            else:
                print("  Bitbucket credentials are invalid")
                issues.append("Bitbucket: App password is invalid or expired")
        except Exception:
            print("  Bitbucket credentials test failed")
            issues.append("Bitbucket: Could not verify credentials")
    else:
        print("\nBitbucket credentials: Not configured (optional)")

    # Summary
    print("\n" + "=" * 40)
    if not issues:
        print("All tests passed")
    else:
        print("Issues found:\n")
        for issue in issues:
            print(f"  - {issue}")
        print("\nRun 'python setup.py' to reconfigure.")

    return len(issues) == 0


def show_status():
    """Display current configuration status."""
    print("WhatThePatch - Status\n")
    print("=" * 50)

    # Check if config exists
    config_path = get_file_path("config.yaml")
    if not config_path.exists():
        print(f"\nConfig file: NOT FOUND")
        print(f"  Expected at: {config_path}")
        print("\nRun 'python setup.py' to configure.")
        return

    print(f"\nConfig file: {config_path}")

    config = load_config()

    # Active engine
    engine_name = config.get("engine", "claude-api")
    print(f"\n--- Active AI Engine ---")
    print(f"Engine: {engine_name}")

    try:
        from engines import get_engine, list_engines, EngineError

        # Show available engines
        available = list_engines()
        print(f"Available engines: {', '.join(available)}")

        # Show engine config
        engine_config = config.get("engines", {}).get(engine_name, {})
        if engine_name == "claude-api":
            api_key = engine_config.get("api_key", "")
            if api_key and not api_key.startswith("sk-ant-api03-..."):
                print(f"API Key: Configured ({api_key[:12]}...)")
            else:
                print(f"API Key: Not configured")
            print(f"Model: {engine_config.get('model', 'claude-sonnet-4-20250514')}")
            print(f"Max Tokens: {engine_config.get('max_tokens', 4096)}")
        elif engine_name == "claude-cli":
            cli_path = engine_config.get("path", "")
            if cli_path:
                print(f"CLI Path: {cli_path}")
            else:
                print(f"CLI Path: System PATH (default)")
            args = engine_config.get("args", [])
            if args:
                print(f"Extra Args: {args}")
        elif engine_name == "openai-api":
            api_key = engine_config.get("api_key", "")
            if api_key and not api_key.startswith("sk-..."):
                print(f"API Key: Configured ({api_key[:12]}...)")
            else:
                print(f"API Key: Not configured")
            print(f"Model: {engine_config.get('model', 'gpt-4o')}")
            print(f"Max Tokens: {engine_config.get('max_tokens', 4096)}")
        elif engine_name == "openai-codex-cli":
            cli_path = engine_config.get("path", "")
            if cli_path:
                print(f"CLI Path: {cli_path}")
            else:
                print(f"CLI Path: System PATH (default)")
            print(f"Model: {engine_config.get('model', 'gpt-5-codex')}")
            api_key = engine_config.get("api_key", "")
            if api_key:
                print(f"API Key: Configured ({api_key[:12]}...)")
            else:
                print(f"API Key: Using ChatGPT sign-in")

        # Validate engine
        try:
            engine = get_engine(engine_name, config)
            is_valid, error = engine.validate_config()
            if is_valid:
                print(f"Status: Ready")
            else:
                print(f"Status: Configuration error - {error}")
        except EngineError as e:
            print(f"Status: Error - {e}")

    except ImportError as e:
        print(f"Engines module: NOT LOADED ({e})")

    # Repository access
    print(f"\n--- Repository Access ---")
    tokens = config.get("tokens", {})

    github_token = tokens.get("github", "")
    if github_token:
        print(f"GitHub: Configured ({github_token[:8]}...)")
    else:
        print(f"GitHub: Not configured")

    bb_user = tokens.get("bitbucket_username", "")
    bb_pass = tokens.get("bitbucket_app_password", "")
    if bb_user and bb_pass:
        print(f"Bitbucket: Configured (user: {bb_user})")
    else:
        print(f"Bitbucket: Not configured")

    # Output settings
    print(f"\n--- Output Settings ---")
    output = config.get("output", {})
    output_dir = output.get("directory", "~/pr-reviews")
    print(f"Directory: {output_dir}")
    print(f"Filename pattern: {output.get('filename_pattern', '{repo}-{pr_number}.md')}")
    print(f"Format: {output.get('format', 'html')}")
    print(f"Auto-open: {'Yes' if output.get('auto_open', True) else 'No'}")

    # Ticket extraction
    print(f"\n--- Ticket Extraction ---")
    ticket = config.get("ticket", {})
    print(f"Pattern: {ticket.get('pattern', '([A-Z]+-\\d+)')}")
    print(f"Fallback: {ticket.get('fallback', 'NO-TICKET')}")

    # Install info
    print(f"\n--- Installation ---")
    print(f"Install directory: {INSTALL_DIR}")
    if INSTALL_DIR.exists():
        print(f"Status: Installed")
    else:
        print(f"Status: Running from source")

    print("\n" + "=" * 50)
    print("\nCommands:")
    print("  wtp --switch-engine  Switch to a different AI engine")
    print("  wtp --switch-output  Switch output format (html, md, txt)")
    print("  wtp --test-config    Run full configuration tests")
    print("  wtp --edit-prompt    Customize review prompt")


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
        # Check if codex is available
        cli_path = engine_config.get("path", "") or shutil.which("codex")
        if cli_path:
            return True, f"CLI available"
        return False, "codex command not found"

    return False, "Unknown engine"


def switch_engine():
    """Interactive engine switcher."""
    print("WhatThePatch - Switch Engine\n")
    print("=" * 50)

    # Check if config exists
    config_path = get_file_path("config.yaml")
    if not config_path.exists():
        print(f"\nConfig file not found at: {config_path}")
        print("Run 'python setup.py' to configure first.")
        return

    config = load_config()
    current_engine = config.get("engine", "claude-api")

    try:
        from engines import list_engines
        available_engines = list_engines()
    except ImportError:
        print("Error: Could not load engines module.")
        print("Run 'python setup.py' to reinstall.")
        return

    # Display current engine and all options
    print(f"\nCurrent engine: {current_engine}")
    print(f"\nAvailable engines:\n")

    engine_status = {}
    for i, engine_name in enumerate(available_engines, 1):
        is_configured, status_msg = get_engine_config_status(engine_name, config)
        engine_status[engine_name] = is_configured

        active_marker = " (active)" if engine_name == current_engine else ""
        config_marker = "Ready" if is_configured else "Not configured"

        print(f"  {i}. {engine_name}{active_marker}")
        print(f"     Status: {config_marker} - {status_msg}")
        print()

    # Prompt for selection
    print("-" * 50)
    print("Enter the number of the engine to switch to,")
    print("or 's' to set up a new engine, or 'q' to quit.")
    print()

    while True:
        choice = input("Your choice: ").strip().lower()

        if choice == 'q':
            print("No changes made.")
            return

        if choice == 's':
            print("\nTo set up a new engine, run: python setup.py")
            return

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(available_engines):
                selected_engine = available_engines[choice_num - 1]
                break
            else:
                print(f"Please enter a number between 1 and {len(available_engines)}")
        except ValueError:
            print("Invalid input. Enter a number, 's', or 'q'.")

    # Check if selected engine is configured
    if not engine_status[selected_engine]:
        print(f"\nWarning: {selected_engine} is not fully configured.")
        confirm = input("Switch anyway? (y/n): ").strip().lower()
        if confirm != 'y':
            print("No changes made.")
            return

    # Update config file
    if selected_engine == current_engine:
        print(f"\n{selected_engine} is already the active engine.")
        return

    try:
        # Read the raw config file to preserve formatting/comments
        with open(config_path, 'r') as f:
            config_content = f.read()

        # Replace the engine line
        # Match: engine: "anything" or engine: 'anything' or engine: anything
        import re
        new_content = re.sub(
            r'^(engine:\s*)["\']?[\w-]+["\']?\s*$',
            f'engine: "{selected_engine}"',
            config_content,
            flags=re.MULTILINE
        )

        if new_content == config_content:
            # If regex didn't match, the format might be different
            # Fall back to full YAML rewrite
            config["engine"] = selected_engine
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        else:
            with open(config_path, 'w') as f:
                f.write(new_content)

        print(f"\nSwitched to: {selected_engine}")
        print(f"Config updated: {config_path}")

        if not engine_status[selected_engine]:
            print(f"\nRemember to configure {selected_engine} in config.yaml")
            print("or run 'python setup.py' for guided setup.")

    except Exception as e:
        print(f"\nError updating config: {e}")
        print("Please update config.yaml manually.")


def switch_output():
    """Interactive output format switcher."""
    print("WhatThePatch - Switch Output Format\n")
    print("=" * 50)

    # Check if config exists
    config_path = get_file_path("config.yaml")
    if not config_path.exists():
        print(f"\nConfig file not found at: {config_path}")
        print("Run 'python setup.py' to configure first.")
        return

    config = load_config()
    current_format = config.get("output", {}).get("format", "html")

    available_formats = [
        ("html", "Styled HTML with GitHub-like formatting, opens in browser"),
        ("md", "Markdown format, opens in default text editor"),
        ("txt", "Plain text format, opens in default text editor"),
    ]

    # Display current format and all options
    print(f"\nCurrent format: {current_format}")
    print(f"\nAvailable formats:\n")

    for i, (fmt, description) in enumerate(available_formats, 1):
        active_marker = " (active)" if fmt == current_format else ""
        print(f"  {i}. {fmt}{active_marker}")
        print(f"     {description}")
        print()

    # Prompt for selection
    print("-" * 50)
    print("Enter the number of the format to switch to,")
    print("or 'q' to quit.")
    print()

    while True:
        choice = input("Your choice: ").strip().lower()

        if choice == 'q':
            print("No changes made.")
            return

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(available_formats):
                selected_format = available_formats[choice_num - 1][0]
                break
            else:
                print(f"Please enter a number between 1 and {len(available_formats)}")
        except ValueError:
            print("Invalid input. Enter a number or 'q'.")

    # Update config file
    if selected_format == current_format:
        print(f"\n{selected_format} is already the active format.")
        return

    try:
        # Read the raw config file to preserve formatting/comments
        with open(config_path, 'r') as f:
            config_content = f.read()

        # Replace the format line under output section
        # Match: format: "anything" or format: 'anything' or format: anything
        new_content = re.sub(
            r'^(\s*format:\s*)["\']?[\w]+["\']?\s*$',
            f'\\1"{selected_format}"',
            config_content,
            flags=re.MULTILINE
        )

        if new_content == config_content:
            # If regex didn't match, fall back to full YAML rewrite
            if "output" not in config:
                config["output"] = {}
            config["output"]["format"] = selected_format
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        else:
            with open(config_path, 'w') as f:
                f.write(new_content)

        print(f"\nSwitched to: {selected_format}")
        print(f"Config updated: {config_path}")

    except Exception as e:
        print(f"\nError updating config: {e}")
        print("Please update config.yaml manually.")


def show_prompt():
    """Display the current review prompt template."""
    prompt_path = get_file_path("prompt.md")

    if not prompt_path.exists():
        print(f"Error: prompt.md not found at {prompt_path}")
        print("Run 'python setup.py' to install WhatThePatch.")
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
        print(f"Error: prompt.md not found at {prompt_path}")
        print("Run 'python setup.py' to install WhatThePatch.")
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
    "prompt.md",
    "engines/__init__.py",
    "engines/base.py",
    "engines/claude_api.py",
    "engines/claude_cli.py",
    "engines/openai_api.py",
    "engines/openai_codex_cli.py",
]


def run_update():
    """Update WhatThePatch from GitHub."""
    print("Updating WhatThePatch...\n")
    print(f"Install directory: {INSTALL_DIR}")
    print(f"Source: github.com/{GITHUB_REPO}\n")

    if not INSTALL_DIR.exists():
        print(f"Error: Install directory not found at {INSTALL_DIR}")
        print("Please run setup.py first to install WhatThePatch.")
        sys.exit(1)

    # Ensure engines directory exists
    engines_dir = INSTALL_DIR / "engines"
    engines_dir.mkdir(parents=True, exist_ok=True)

    updated = []
    failed = []

    for filename in UPDATABLE_FILES:
        url = f"{GITHUB_RAW_BASE}/{filename}"
        dest = INSTALL_DIR / filename

        # Ensure parent directory exists for nested files
        dest.parent.mkdir(parents=True, exist_ok=True)

        print(f"Downloading {filename}...", end=" ")
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                dest.write_text(response.text)
                print("OK")
                updated.append(filename)
            else:
                print(f"FAILED (HTTP {response.status_code})")
                failed.append(filename)
        except Exception as e:
            print(f"FAILED ({e})")
            failed.append(filename)

    print()
    if updated:
        print(f"Updated: {len(updated)} files")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        print("\nTo update manually:")
        print(f"  1. Clone the repo: git clone https://github.com/{GITHUB_REPO}")
        print(f"  2. Run setup.py from the cloned repo")

    if updated and not failed:
        print("\nUpdate complete!")


def main():
    parser = argparse.ArgumentParser(
        prog="wtp",
        description="WhatThePatch - Generate AI-powered PR reviews",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  wtp --review https://github.com/owner/repo/pull/123
  wtp --review https://bitbucket.org/workspace/repo/pull-requests/456
  wtp --status
  wtp --switch-engine
  wtp --switch-output
  wtp --test-config
  wtp --update
  wtp --show-prompt
  wtp --edit-prompt

Author:
  Aaron Medina
  GitHub:   https://github.com/aaronmedina-dev
  LinkedIn: https://www.linkedin.com/in/aamedina/
""",
    )
    parser.add_argument(
        "--review", "-r",
        metavar="URL",
        help="URL of the pull request to review",
    )
    parser.add_argument(
        "--test-config",
        action="store_true",
        help="Test the current configuration",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update the tool from the git repository",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="Display the current review prompt template",
    )
    parser.add_argument(
        "--edit-prompt",
        action="store_true",
        help="Open the prompt template in your editor",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current configuration and active AI engine",
    )
    parser.add_argument(
        "--switch-engine",
        action="store_true",
        help="Switch between configured AI engines",
    )
    parser.add_argument(
        "--switch-output",
        action="store_true",
        help="Switch between output formats (html, md, txt)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["md", "txt", "html"],
        metavar="FORMAT",
        help="Output format: html (default), md, or txt",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't auto-open the output file after generation",
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
        return

    if args.switch_engine:
        switch_engine()
        return

    if args.switch_output:
        switch_output()
        return

    if args.test_config:
        success = run_config_test()
        sys.exit(0 if success else 1)

    if not args.review:
        parser.print_help()
        sys.exit(1)

    print(f"Loading configuration...")
    config = load_config()

    print(f"Parsing PR URL...")
    pr_info = parse_pr_url(args.review)
    print(f"  Platform: {pr_info['platform']}")
    print(f"  Repository: {pr_info['owner']}/{pr_info['repo']}")
    print(f"  PR Number: {pr_info['pr_number']}")

    print(f"Fetching PR data...")
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

    print(f"  Title: {pr_data['title']}")
    print(f"  Branch: {pr_data['source_branch']} -> {pr_data['target_branch']}")

    ticket_id = extract_ticket_id(
        pr_data["source_branch"],
        config["ticket"]["pattern"],
        config["ticket"]["fallback"],
    )
    print(f"  Ticket ID: {ticket_id}")

    diff_lines = pr_data["diff"].count("\n")
    print(f"  Diff size: {diff_lines} lines")

    engine_name = config.get("engine", "claude-api")
    try:
        from engines import get_engine
        engine = get_engine(engine_name, config)
        engine_label = engine.name
    except Exception:
        engine_label = engine_name
    print(f"Generating review with {engine_label}...")
    review = generate_review(pr_data, ticket_id, config)

    # Determine output format (CLI arg overrides config)
    output_format = args.format or config.get("output", {}).get("format", "html")
    print(f"Saving review ({output_format} format)...")
    output_path = save_review(review, pr_info, ticket_id, pr_data, config, output_format)

    print(f"\nReview saved to: {output_path}")

    # Auto-open file if enabled (config default is True, --no-open disables)
    auto_open = config.get("output", {}).get("auto_open", True)
    if auto_open and not args.no_open:
        print(f"Opening file...")
        auto_open_file(output_path)


if __name__ == "__main__":
    main()
