"""
Warning suppression configuration for WhatThePatch.

This module handles configurable warning suppression. Import it early
(before other imports that may trigger warnings) in the main entry point.

Warnings can be suppressed via config.yaml settings.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

# Define suppressible warnings with their configuration
# Each warning has:
#   - pattern: Regex pattern to match the warning message
#   - module: Module that generates the warning (for targeted filtering)
#   - config_key: Key in config.yaml to enable suppression
#   - hint: Message shown to user when warning appears (if not suppressed)
SUPPRESSIBLE_WARNINGS = {
    "ssl_warning": {
        "pattern": r".*urllib3.*OpenSSL.*|.*NotOpenSSLWarning.*",
        "module": r"urllib3.*",
        "config_key": "suppress_ssl_warning",
        "hint": (
            "To suppress this warning, add to your config.yaml:\n"
            "  suppress_ssl_warning: true\n"
            "This warning does not affect functionality."
        ),
    },
    # Future warnings can be added here, e.g.:
    # "deprecation_warning": {
    #     "pattern": r".*DeprecationWarning.*",
    #     "module": r".*",
    #     "config_key": "suppress_deprecation_warnings",
    #     "hint": "Add 'suppress_deprecation_warnings: true' to config.yaml",
    # },
}


def _get_config_path() -> Optional[Path]:
    """Get the path to config.yaml without importing other modules."""
    # Check local directory first
    local_config = Path("config.yaml")
    if local_config.exists():
        return local_config

    # Check install directory
    install_config = Path.home() / ".whatthepatch" / "config.yaml"
    if install_config.exists():
        return install_config

    return None


def _load_config_value(key: str) -> Optional[bool]:
    """Load a specific config value without full YAML parsing if possible."""
    config_path = _get_config_path()
    if not config_path:
        return None

    try:
        # Simple line-based parsing for boolean config values
        # This avoids importing yaml before we've configured warnings
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}:"):
                    value = line.split(":", 1)[1].strip().lower()
                    if value in ("true", "yes", "1"):
                        return True
                    elif value in ("false", "no", "0"):
                        return False
    except Exception:
        pass

    return None


def _show_warning_with_hint(message: str, category: type, filename: str, lineno: int, file=None, line=None):
    """Custom warning handler that shows the hint for suppressible warnings."""
    import sys

    # Format the warning message
    warning_text = f"{filename}:{lineno}: {category.__name__}: {message}\n"
    sys.stderr.write(warning_text)

    # Check if this matches any suppressible warning and show hint
    for warning_id, warning_info in SUPPRESSIBLE_WARNINGS.items():
        import re
        if re.match(warning_info["pattern"], str(message), re.IGNORECASE):
            config_key = warning_info["config_key"]
            # Only show hint if not already suppressed
            if not _load_config_value(config_key):
                hint = warning_info["hint"]
                sys.stderr.write(f"\nHint: {hint}\n\n")
            break


def configure_warnings():
    """
    Configure warning suppression based on config.yaml settings.

    Call this early in the application startup, before importing
    modules that may trigger warnings (like requests/urllib3).
    """
    for warning_id, warning_info in SUPPRESSIBLE_WARNINGS.items():
        config_key = warning_info["config_key"]
        should_suppress = _load_config_value(config_key)

        if should_suppress:
            # Suppress the warning entirely
            warnings.filterwarnings(
                "ignore",
                message=warning_info["pattern"],
                module=warning_info.get("module", ""),
            )


def show_suppression_hint(warning_id: str) -> Optional[str]:
    """
    Get the suppression hint for a specific warning.

    Args:
        warning_id: The warning identifier (e.g., "ssl_warning")

    Returns:
        The hint text, or None if warning_id not found
    """
    warning_info = SUPPRESSIBLE_WARNINGS.get(warning_id)
    if warning_info:
        return warning_info["hint"]
    return None


# Auto-configure warnings when this module is imported
configure_warnings()
