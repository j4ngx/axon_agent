"""Axon domain exceptions.

A small hierarchy so callers can catch at the appropriate granularity without
relying on bare ``Exception``.
"""


class AxonError(Exception):
    """Base exception for all Axon-specific errors."""


class LLMError(AxonError):
    """Raised when an LLM backend call fails irrecoverably."""


class ToolError(AxonError):
    """Raised when a tool invocation fails."""


class PersistenceError(AxonError):
    """Raised when the persistence layer encounters an error."""


class AuthorizationError(AxonError):
    """Raised when an unauthorised user attempts to interact with Axon."""
