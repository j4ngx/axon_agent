"""Tests for the ``FallbackLLMClient``."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from helix.exceptions import LLMError
from helix.llm.base import LLMResponse
from helix.llm.fallback import FallbackLLMClient


class TestFallbackLLMClient:
    """Unit tests for ``FallbackLLMClient``."""

    async def test_when_primary_succeeds_expect_primary_result(self) -> None:
        # Arrange
        primary = AsyncMock()
        primary.generate.return_value = LLMResponse(content="from primary")
        fallback = AsyncMock()
        client = FallbackLLMClient(primary=primary, fallback=fallback)

        # Act
        result = await client.generate([{"role": "user", "content": "hi"}])

        # Assert
        assert result.content == "from primary"
        primary.generate.assert_called_once()
        fallback.generate.assert_not_called()

    async def test_when_primary_fails_expect_fallback_used(self) -> None:
        # Arrange
        primary = AsyncMock()
        primary.generate.side_effect = LLMError("primary down")
        fallback = AsyncMock()
        fallback.generate.return_value = LLMResponse(content="from fallback")
        client = FallbackLLMClient(primary=primary, fallback=fallback)

        # Act
        result = await client.generate([{"role": "user", "content": "hi"}])

        # Assert
        assert result.content == "from fallback"
        primary.generate.assert_called_once()
        fallback.generate.assert_called_once()

    async def test_when_both_fail_expect_llm_error(self) -> None:
        # Arrange
        primary = AsyncMock()
        primary.generate.side_effect = LLMError("primary down")
        fallback = AsyncMock()
        fallback.generate.side_effect = LLMError("fallback down")
        client = FallbackLLMClient(primary=primary, fallback=fallback)

        # Act & Assert
        with pytest.raises(LLMError, match="Both LLM backends failed"):
            await client.generate([{"role": "user", "content": "hi"}])
