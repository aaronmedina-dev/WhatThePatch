"""
WhatThePatch - PR Providers

This module handles fetching pull request data from GitHub and Bitbucket.
Includes URL parsing, API calls, and diff retrieval.
"""

from __future__ import annotations

import re
import sys
from urllib.parse import urlparse

import requests


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


def fetch_github_pr_files(owner: str, repo: str, pr_number: str, token: str) -> tuple[str, int, int]:
    """
    Fetch PR diff using the files API (fallback for large PRs).

    Returns:
        Tuple of (reconstructed_diff, file_count, truncated_count)
    """
    from cli_utils import print_warning

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    all_files = []
    page = 1
    per_page = 100  # Max allowed by GitHub

    # Paginate through all files (up to 3000 max)
    while True:
        response = requests.get(
            files_url,
            headers=headers,
            params={"page": page, "per_page": per_page}
        )

        if response.status_code != 200:
            from cli_utils import print_cli_error
            print_cli_error(
                f"Error fetching PR files from GitHub: {response.status_code}",
                hints=["Check your GitHub token permissions"]
            )
            sys.exit(1)

        files = response.json()
        if not files:
            break

        all_files.extend(files)
        page += 1

        # Safety limit
        if page > 50:  # 50 * 100 = 5000 files max
            print_warning("PR has more than 5000 files, truncating...")
            break

    # Reconstruct diff from patches
    diff_parts = []
    truncated_count = 0

    for file in all_files:
        filename = file.get("filename", "unknown")
        status = file.get("status", "modified")
        patch = file.get("patch")

        # Build diff header
        if status == "added":
            diff_parts.append(f"diff --git a/{filename} b/{filename}")
            diff_parts.append("new file mode 100644")
            diff_parts.append(f"--- /dev/null")
            diff_parts.append(f"+++ b/{filename}")
        elif status == "removed":
            diff_parts.append(f"diff --git a/{filename} b/{filename}")
            diff_parts.append("deleted file mode 100644")
            diff_parts.append(f"--- a/{filename}")
            diff_parts.append(f"+++ /dev/null")
        elif status == "renamed":
            prev_filename = file.get("previous_filename", filename)
            diff_parts.append(f"diff --git a/{prev_filename} b/{filename}")
            diff_parts.append(f"rename from {prev_filename}")
            diff_parts.append(f"rename to {filename}")
            if patch:
                diff_parts.append(f"--- a/{prev_filename}")
                diff_parts.append(f"+++ b/{filename}")
        else:  # modified
            diff_parts.append(f"diff --git a/{filename} b/{filename}")
            diff_parts.append(f"--- a/{filename}")
            diff_parts.append(f"+++ b/{filename}")

        # Add patch content if available
        if patch:
            diff_parts.append(patch)
        elif file.get("additions", 0) > 0 or file.get("deletions", 0) > 0:
            # File has changes but patch is truncated
            truncated_count += 1
            diff_parts.append(f"@@ Patch truncated - file too large ({file.get('additions', 0)}+ {file.get('deletions', 0)}-) @@")

        diff_parts.append("")  # Empty line between files

    return "\n".join(diff_parts), len(all_files), truncated_count


def fetch_github_pr(owner: str, repo: str, pr_number: str, token: str) -> dict:
    """Fetch PR details and diff from GitHub API."""
    from cli_utils import print_warning

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

    # Try to fetch diff directly first
    headers["Accept"] = "application/vnd.github.v3.diff"
    diff_response = requests.get(pr_url, headers=headers)

    if diff_response.status_code == 200:
        diff = diff_response.text
    elif diff_response.status_code == 406:
        # Diff too large - fall back to files API
        print_warning(
            f"PR exceeds GitHub's diff limit (300 files). "
            f"Fetching via files API (supports up to 3000 files)..."
        )
        diff, file_count, truncated_count = fetch_github_pr_files(owner, repo, pr_number, token)

        if truncated_count > 0:
            print_warning(
                f"Fetched {file_count} files. "
                f"{truncated_count} file(s) had truncated patches (files too large)."
            )
        else:
            print_warning(f"Fetched {file_count} files successfully.")
    else:
        print(f"Error fetching diff from GitHub: {diff_response.status_code}")
        sys.exit(1)

    return {
        "title": pr_data["title"],
        "description": pr_data.get("body") or "(No description provided)",
        "source_branch": pr_data["head"]["ref"],
        "target_branch": pr_data["base"]["ref"],
        "diff": diff,
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
