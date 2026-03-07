"""Helix domain exceptions.

A small hierarchy so callers can catch at the appropriate granularity without
relying on bare ``Exception``.
"""


class HelixError(Exception):
    """Base exception for all Helix-specific errors."""


class LLMError(HelixError):
    """Raised when an LLM backend call fails irrecoverably."""


class ToolError(HelixError):
    """Raised when a tool invocation fails."""


class PersistenceError(HelixError):
    """Raised when the persistence layer encounters an error."""


class AuthorizationError(HelixError):
    """Raised when an unauthorised user attempts to interact with Helix."""
