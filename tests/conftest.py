"""
Shared pytest fixtures for WhatThePatch tests.
"""

import sys
from pathlib import Path

import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_config_full():
    """A complete mock configuration with all engines configured."""
    return {
        "engine": "claude-api",
        "engines": {
            "claude-api": {
                "api_key": "sk-ant-api03-real-key-here",
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "available_models": [
                    "claude-sonnet-4-20250514",
                    "claude-opus-4-20250514",
                    "claude-3-5-sonnet-20241022",
                ],
            },
            "claude-cli": {
                "path": "",
                "args": ["--model", "opus"],
            },
            "openai-api": {
                "api_key": "sk-real-openai-key",
                "model": "gpt-4o",
                "max_tokens": 4096,
                "available_models": [
                    "gpt-4o",
                    "gpt-4o-mini",
                    "o1",
                ],
            },
            "openai-codex-cli": {
                "path": "",
                "model": "gpt-5",
            },
            "gemini-api": {
                "api_key": "AIza-real-gemini-key",
                "model": "gemini-2.0-flash",
                "max_tokens": 4096,
                "available_models": [
                    "gemini-2.0-flash",
                    "gemini-1.5-pro",
                ],
            },
            "gemini-cli": {
                "path": "",
                "model": "gemini-2.0-flash",
            },
        },
        "tokens": {
            "github": "ghp_test_token",
            "bitbucket_username": "test_user",
            "bitbucket_app_password": "test_password",
        },
        "output": {
            "directory": "~/pr-reviews",
            "filename_pattern": "{repo}-{pr_number}",
            "format": "html",
            "auto_open": True,
        },
        "ticket": {
            "pattern": r"([A-Z]+-\d+)",
            "fallback": "NO-TICKET",
        },
    }


@pytest.fixture
def mock_config_minimal():
    """A minimal mock configuration with placeholder API keys."""
    return {
        "engine": "claude-api",
        "engines": {
            "claude-api": {
                "api_key": "sk-ant-api03-...",
                "model": "claude-sonnet-4-20250514",
            },
            "openai-api": {
                "api_key": "sk-...",
            },
            "gemini-api": {
                "api_key": "AIza...",
            },
        },
        "tokens": {},
        "output": {
            "directory": "~/pr-reviews",
            "format": "html",
        },
    }


@pytest.fixture
def mock_config_empty():
    """An empty mock configuration."""
    return {
        "engine": "claude-api",
        "engines": {},
        "tokens": {},
        "output": {},
    }


@pytest.fixture
def mock_pr_data():
    """Mock pull request data for testing."""
    return {
        "title": "Add user authentication feature",
        "description": "This PR implements OAuth2 authentication for users.",
        "source_branch": "feature/PROJ-123-user-auth",
        "target_branch": "main",
        "diff": """\
diff --git a/src/auth.py b/src/auth.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/auth.py
@@ -0,0 +1,20 @@
+def authenticate_user(token):
+    \"\"\"Authenticate a user with the given token.\"\"\"
+    if not token:
+        return None
+    return verify_token(token)
""",
        "author": "testuser",
        "pr_url": "https://github.com/owner/repo/pull/123",
    }


@pytest.fixture
def sample_branch_names():
    """Sample branch names for ticket extraction testing."""
    return [
        ("feature/PROJ-123-add-auth", "PROJ-123"),
        ("bugfix/BUG-456-fix-login", "BUG-456"),
        ("JIRA-789-update-readme", "JIRA-789"),
        ("feature/no-ticket-here", "NO-TICKET"),
        ("main", "NO-TICKET"),
        ("develop", "NO-TICKET"),
    ]
