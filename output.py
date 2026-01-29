"""
WhatThePatch - Output Handling

This module handles saving and formatting PR reviews:
- save_review: Save review to file with proper formatting
- convert_to_html: Convert markdown to styled HTML
- auto_open_file: Open file in default application
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import webbrowser
from pathlib import Path

from cli_utils import (
    console,
    print_warning,
)
from pr_providers import sanitize_filename


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


