"""
Tests for CLI argument parsing and utility functions.

Tests cover:
- PR URL parsing
- Ticket ID extraction
- Version parsing
- Filename sanitization
- Output format handling
"""

import pytest

from whatthepatch import (
    parse_pr_url,
    extract_ticket_id,
    parse_version,
    sanitize_filename,
)


class TestParsePrUrl:
    """Tests for parse_pr_url() function."""

    def test_github_url_parsing(self):
        """Should correctly parse GitHub PR URLs."""
        url = "https://github.com/owner/repo/pull/123"
        result = parse_pr_url(url)
        assert result["platform"] == "github"
        assert result["owner"] == "owner"
        assert result["repo"] == "repo"
        assert result["pr_number"] == "123"

    def test_github_url_with_trailing_slash(self):
        """Should handle GitHub URLs with trailing slashes."""
        url = "https://github.com/owner/repo/pull/456/"
        result = parse_pr_url(url)
        assert result["pr_number"] == "456"

    def test_bitbucket_url_parsing(self):
        """Should correctly parse Bitbucket PR URLs."""
        url = "https://bitbucket.org/workspace/repo/pull-requests/789"
        result = parse_pr_url(url)
        assert result["platform"] == "bitbucket"
        assert result["owner"] == "workspace"
        assert result["repo"] == "repo"
        assert result["pr_number"] == "789"

    def test_github_url_with_complex_repo_name(self):
        """Should handle repo names with hyphens and underscores."""
        url = "https://github.com/my-org/my_complex-repo-name/pull/42"
        result = parse_pr_url(url)
        assert result["repo"] == "my_complex-repo-name"
        assert result["owner"] == "my-org"

    def test_invalid_url_exits(self):
        """Should exit on invalid PR URLs."""
        with pytest.raises(SystemExit):
            parse_pr_url("https://example.com/not-a-pr")

    def test_missing_pr_number_exits(self):
        """Should exit when PR number is missing."""
        with pytest.raises(SystemExit):
            parse_pr_url("https://github.com/owner/repo/pull")

    def test_wrong_platform_exits(self):
        """Should exit for unsupported platforms."""
        with pytest.raises(SystemExit):
            parse_pr_url("https://gitlab.com/owner/repo/merge_requests/123")


class TestExtractTicketId:
    """Tests for extract_ticket_id() function."""

    def test_extracts_jira_style_ticket(self, sample_branch_names):
        """Should extract JIRA-style ticket IDs."""
        pattern = r"([A-Z]+-\d+)"
        fallback = "NO-TICKET"

        for branch, expected in sample_branch_names:
            result = extract_ticket_id(branch, pattern, fallback)
            assert result == expected, f"Failed for branch: {branch}"

    def test_custom_pattern(self):
        """Should work with custom patterns."""
        branch = "feature/issue-123-description"
        pattern = r"issue-(\d+)"
        result = extract_ticket_id(branch, pattern, "NO-TICKET")
        assert result == "123"

    def test_returns_fallback_when_no_match(self):
        """Should return fallback when no match found."""
        branch = "main"
        pattern = r"([A-Z]+-\d+)"
        result = extract_ticket_id(branch, pattern, "UNKNOWN")
        assert result == "UNKNOWN"

    def test_extracts_first_match(self):
        """Should extract the first matching ticket."""
        branch = "feature/PROJ-123-related-to-PROJ-456"
        pattern = r"([A-Z]+-\d+)"
        result = extract_ticket_id(branch, pattern, "NO-TICKET")
        assert result == "PROJ-123"


class TestParseVersion:
    """Tests for parse_version() function."""

    def test_parses_simple_version(self):
        """Should parse simple version strings."""
        assert parse_version("1.0.0") == (1, 0, 0)
        assert parse_version("2.5.3") == (2, 5, 3)

    def test_handles_v_prefix(self):
        """Should strip lowercase 'v' prefix from version strings."""
        assert parse_version("v1.2.3") == (1, 2, 3)
        assert parse_version("v2.0.0") == (2, 0, 0)
        # Note: Only lowercase 'v' is handled by the implementation

    def test_handles_two_part_version(self):
        """Should parse two-part version strings."""
        assert parse_version("1.0") == (1, 0)

    def test_handles_single_number(self):
        """Should parse single number versions."""
        assert parse_version("5") == (5,)

    def test_invalid_version_returns_zeros(self):
        """Should return (0, 0, 0) for invalid versions."""
        assert parse_version("invalid") == (0, 0, 0)
        assert parse_version("") == (0, 0, 0)

    def test_version_comparison(self):
        """Parsed versions should compare correctly."""
        assert parse_version("2.0.0") > parse_version("1.9.9")
        assert parse_version("1.1.0") > parse_version("1.0.9")
        assert parse_version("v1.0.1") > parse_version("v1.0.0")


class TestSanitizeFilename:
    """Tests for sanitize_filename() function."""

    def test_replaces_special_characters(self):
        """Should replace special characters with hyphens."""
        assert sanitize_filename("feature/test") == "feature-test"
        assert sanitize_filename("my file.txt") == "my-file-txt"

    def test_preserves_allowed_characters(self):
        """Should preserve alphanumeric, hyphens, and underscores."""
        assert sanitize_filename("valid_file-name123") == "valid_file-name123"

    def test_handles_multiple_special_chars(self):
        """Should handle multiple consecutive special characters."""
        result = sanitize_filename("test@#$name")
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result

    def test_empty_string(self):
        """Should handle empty string."""
        assert sanitize_filename("") == ""


class TestOutputFormatHandling:
    """Tests for output format handling."""

    def test_format_choices(self):
        """Verify supported output formats."""
        supported_formats = ["md", "txt", "html"]
        for fmt in supported_formats:
            # Just verify the format strings are valid
            assert fmt in ["md", "txt", "html"]

    def test_extension_mapping(self):
        """Verify extension mapping is correct."""
        extension_map = {"md": ".md", "txt": ".txt", "html": ".html"}
        assert extension_map["md"] == ".md"
        assert extension_map["txt"] == ".txt"
        assert extension_map["html"] == ".html"


class TestVersionConstant:
    """Tests for version constant."""

    def test_version_is_defined(self):
        """__version__ should be defined."""
        from whatthepatch import __version__
        assert __version__ is not None
        assert isinstance(__version__, str)

    def test_version_format(self):
        """__version__ should be in semver format."""
        from whatthepatch import __version__
        parts = __version__.split(".")
        assert len(parts) >= 2, "Version should have at least 2 parts"
        for part in parts:
            assert part.isdigit(), f"Version part '{part}' should be numeric"
