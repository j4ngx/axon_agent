"""Tests for Telegram handlers, auth middleware, and helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aiogram import types

from helix.telegram.handlers import (
    AuthMiddleware,
    _escape_markdown,
    _split_message,
)

# ---------------------------------------------------------------------------
# AuthMiddleware
# ---------------------------------------------------------------------------


class TestAuthMiddleware:
    """Unit tests for ``AuthMiddleware``."""

    def setup_method(self) -> None:
        self.middleware = AuthMiddleware(allowed_user_ids={100, 200})

    async def test_when_allowed_user_expect_handler_called(self) -> None:
        # Arrange
        handler = AsyncMock(return_value="ok")
        message = MagicMock(spec=types.Message)
        message.from_user = MagicMock(id=100)
        message.answer = AsyncMock()

        # Act
        result = await self.middleware(handler, message, {})

        # Assert
        handler.assert_called_once_with(message, {})
        assert result == "ok"
        message.answer.assert_not_called()

    async def test_when_blocked_user_expect_rejected(self) -> None:
        # Arrange
        handler = AsyncMock()
        message = MagicMock(spec=types.Message)
        message.from_user = MagicMock(id=999)
        message.answer = AsyncMock()

        # Act
        result = await self.middleware(handler, message, {})

        # Assert
        handler.assert_not_called()
        assert result is None
        message.answer.assert_called_once()
        call_text = message.answer.call_args[0][0]
        assert "not authorised" in call_text

    async def test_when_no_user_expect_rejected(self) -> None:
        # Arrange
        handler = AsyncMock()
        message = MagicMock(spec=types.Message)
        message.from_user = None
        message.answer = AsyncMock()

        # Act
        result = await self.middleware(handler, message, {})

        # Assert
        handler.assert_not_called()
        assert result is None


# ---------------------------------------------------------------------------
# _escape_markdown
# ---------------------------------------------------------------------------


class TestEscapeMarkdown:
    """Unit tests for ``_escape_markdown``."""

    def test_when_plain_text_expect_unchanged(self) -> None:
        assert _escape_markdown("hello world") == "hello world"

    def test_when_underscores_expect_escaped(self) -> None:
        assert _escape_markdown("hello_world") == "hello\\_world"

    def test_when_asterisks_expect_escaped(self) -> None:
        assert _escape_markdown("**bold**") == "\\*\\*bold\\*\\*"

    def test_when_backticks_expect_escaped(self) -> None:
        assert _escape_markdown("`code`") == "\\`code\\`"

    def test_when_brackets_expect_escaped(self) -> None:
        assert _escape_markdown("[link]") == "\\[link]"

    def test_when_mixed_special_chars_expect_all_escaped(self) -> None:
        result = _escape_markdown("_*`[test")
        assert result == "\\_\\*\\`\\[test"

    def test_when_empty_string_expect_empty(self) -> None:
        assert _escape_markdown("") == ""


# ---------------------------------------------------------------------------
# _split_message
# ---------------------------------------------------------------------------


class TestSplitMessage:
    """Unit tests for ``_split_message``."""

    def test_when_short_message_expect_single_chunk(self) -> None:
        result = _split_message("hello")
        assert result == ["hello"]

    def test_when_empty_string_expect_single_chunk(self) -> None:
        result = _split_message("")
        assert result == [""]

    def test_when_exact_limit_expect_single_chunk(self) -> None:
        text = "x" * 4096
        result = _split_message(text)
        assert len(result) == 1
        assert result[0] == text

    def test_when_over_limit_expect_multiple_chunks(self) -> None:
        text = "a" * 5000
        result = _split_message(text, max_length=4096)
        assert len(result) == 2
        assert len(result[0]) == 4096
        assert len(result[1]) == 904

    def test_when_custom_limit_expect_correct_splits(self) -> None:
        text = "abcdef"
        result = _split_message(text, max_length=2)
        assert result == ["ab", "cd", "ef"]
