"""
Base engine interface for AI providers.

All AI engines must inherit from BaseEngine and implement the required methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class EngineError(Exception):
    """Exception raised for engine-related errors."""
    pass


class BaseEngine(ABC):
    """
    Abstract base class for AI engines.

    All engines must implement:
    - generate_review(): Generate a PR review from the given data
    - validate_config(): Check if the engine configuration is valid
    - test_connection(): Test if the engine can connect to the AI provider
    """

    def __init__(self, config: dict):
        """
        Initialize the engine with configuration.

        Args:
            config: Engine-specific configuration dictionary
        """
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the engine."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description of the engine."""
        pass

    @abstractmethod
    def generate_review(
        self,
        pr_data: dict,
        ticket_id: str,
        prompt_template: str,
        external_context: str = "",
    ) -> str:
        """
        Generate a PR review using this engine.

        Args:
            pr_data: Dictionary containing PR information:
                - title: PR title
                - description: PR description
                - source_branch: Source branch name
                - target_branch: Target branch name
                - diff: The diff content
            ticket_id: Extracted ticket ID from branch name
            prompt_template: The review prompt template with placeholders
            external_context: Optional external context from local files/directories

        Returns:
            Generated review as markdown string

        Raises:
            EngineError: If review generation fails
        """
        pass

    @abstractmethod
    def validate_config(self) -> tuple[bool, Optional[str]]:
        """
        Validate the engine configuration.

        Returns:
            Tuple of (is_valid, error_message)
            If valid, returns (True, None)
            If invalid, returns (False, "error description")
        """
        pass

    @abstractmethod
    def test_connection(self) -> tuple[bool, Optional[str]]:
        """
        Test the connection to the AI provider.

        Returns:
            Tuple of (success, error_message)
            If successful, returns (True, None)
            If failed, returns (False, "error description")
        """
        pass

    def build_prompt(
        self,
        pr_data: dict,
        ticket_id: str,
        prompt_template: str,
        external_context: str = "",
    ) -> str:
        """
        Build the full prompt from template and PR data.

        This is a helper method that can be used by all engines.

        Args:
            pr_data: PR information dictionary
            ticket_id: Ticket ID
            prompt_template: Template string with placeholders
            external_context: Optional external context from local files/directories

        Returns:
            Formatted prompt string
        """
        context_section = external_context if external_context else "No external context provided."
        return prompt_template.format(
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
