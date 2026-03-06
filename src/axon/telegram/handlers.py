"""Telegram message handlers and authorization middleware.

All Telegram-specific logic (routing, filtering, auth) lives here and
delegates business work to the agent loop.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Router, types
from aiogram.filters import CommandStart

from axon.agent.loop import AgentLoop

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Authorization middleware
# ---------------------------------------------------------------------------


class AuthMiddleware(BaseMiddleware):
    """Reject messages from users not in the allow-list.

    Args:
        allowed_user_ids: Set of Telegram user IDs that are authorised.
    """

    def __init__(self, allowed_user_ids: set[int]) -> None:
        super().__init__()
        self._allowed = allowed_user_ids

    async def __call__(
        self,
        handler: Callable[[types.Update, dict[str, Any]], Awaitable[Any]],
        event: types.Message,
        data: dict[str, Any],
    ) -> Any:
        """Check authorisation before forwarding to the actual handler."""
        user = event.from_user
        if user is None or user.id not in self._allowed:
            uid = user.id if user else "unknown"
            logger.warning("Unauthorized access attempt", extra={"user_id": uid})
            await event.answer("⛔ You are not authorised to use this bot.")
            return None
        return await handler(event, data)


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def create_router(agent_loop: AgentLoop, allowed_user_ids: list[int]) -> Router:
    """Build the aiogram ``Router`` with auth middleware and handlers.

    Args:
        agent_loop: The agent loop that processes user messages.
        allowed_user_ids: Telegram user IDs allowed to interact with Axon.

    Returns:
        A configured ``Router``.
    """
    router = Router(name="axon_main")
    router.message.middleware(AuthMiddleware(set(allowed_user_ids)))

    # -- /start command -------------------------------------------------

    @router.message(CommandStart())
    async def handle_start(message: types.Message) -> None:
        """Greet the user on ``/start``."""
        await message.answer(
            "👋 Hi! I'm **Axon**, your personal AI assistant.\n\n"
            "Send me any message and I'll do my best to help.",
            parse_mode="Markdown",
        )

    # -- Text messages --------------------------------------------------

    @router.message()
    async def handle_message(message: types.Message) -> None:
        """Route text messages through the agent loop."""
        if not message.text:
            await message.answer("I can only process text messages for now.")
            return

        user_id = message.from_user.id  # type: ignore[union-attr]
        logger.info(
            "Incoming message",
            extra={"user_id": user_id, "length": len(message.text)},
        )

        try:
            reply = await agent_loop.run(user_id=user_id, user_message=message.text)
        except Exception:
            logger.exception("Agent loop error", extra={"user_id": user_id})
            reply = "Something went wrong while processing your message. Please try again."

        # Telegram has a 4096-char limit per message.
        for chunk in _split_message(reply):
            await message.answer(chunk)

    return router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MAX_MESSAGE_LENGTH = 4096


def _split_message(text: str, max_length: int = _MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long message into chunks that fit Telegram's limit.

    Args:
        text: The full reply text.
        max_length: Maximum characters per chunk.

    Returns:
        A list of one or more message chunks.
    """
    if len(text) <= max_length:
        return [text]
    chunks: list[str] = []
    while text:
        chunks.append(text[:max_length])
        text = text[max_length:]
    return chunks
