"""Telegram message handlers and authorization middleware.

All Telegram-specific logic (routing, filtering, auth) lives here and
delegates business work to the agent loop.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot, Router, types
from aiogram.filters import CommandStart

from axon.agent.loop import AgentLoop
from axon.llm.transcription import TranscriptionClient

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


def create_router(
    agent_loop: AgentLoop,
    allowed_user_ids: list[int],
    transcription_client: TranscriptionClient,
    bot: Bot,
) -> Router:
    """Build the aiogram ``Router`` with auth middleware and handlers.

    Args:
        agent_loop: The agent loop that processes user messages.
        allowed_user_ids: Telegram user IDs allowed to interact with Axon.
        transcription_client: Groq Whisper client for voice messages.
        bot: The aiogram Bot instance (needed to fetch file URLs).

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
            "Send me any message — text or a voice note — and I'll do my best to help.",
            parse_mode="Markdown",
        )

    # -- Voice / audio messages -----------------------------------------

    @router.message(lambda m: m.voice is not None or m.audio is not None)
    async def handle_voice(message: types.Message) -> None:
        """Transcribe a voice note or audio file and run it through the agent."""
        user_id = message.from_user.id  # type: ignore[union-attr]

        # Determine the Telegram file object (voice note vs. audio file).
        file_obj = message.voice or message.audio
        if file_obj is None:
            await message.answer("⚠️ Could not read the audio file.")
            return

        logger.info(
            "Incoming voice message",
            extra={"user_id": user_id, "file_id": file_obj.file_id},
        )

        # Show the user we're working on it.
        await message.answer("🎙️ Transcribing your voice message…")

        try:
            # 1. Get the download URL from Telegram.
            file_info = await bot.get_file(file_obj.file_id)
            if file_info.file_path is None:
                await message.answer("⚠️ Could not retrieve the audio file from Telegram.")
                return

            # Determine filename/extension for codec detection.
            file_name = getattr(message.audio, "file_name", None) or f"voice_{file_obj.file_id}.ogg"
            file_url = bot.session.api.file_url(
                bot.token,
                file_info.file_path,
            )

            # 2. Transcribe.
            transcribed_text = await transcription_client.transcribe_from_url(
                file_url=file_url,
                file_name=file_name,
            )
        except Exception:
            logger.exception("Voice transcription failed", extra={"user_id": user_id})
            await message.answer(
                "⚠️ Sorry, I couldn't transcribe that audio. "
                "Please try again or send a text message."
            )
            return

        logger.info(
            "Voice transcribed",
            extra={"user_id": user_id, "text_length": len(transcribed_text)},
        )

        # Echo the transcription so the user can confirm.
        # Escape Markdown special chars to avoid Telegram parse errors.
        safe_text = _escape_markdown(transcribed_text)
        await message.answer(f"🗣️ *Transcription:*\n_{safe_text}_", parse_mode="Markdown")

        # 3. Run through the agent loop as if it were a text message.
        try:
            reply = await agent_loop.run(user_id=user_id, user_message=transcribed_text)
        except Exception:
            logger.exception("Agent loop error after transcription", extra={"user_id": user_id})
            reply = "Something went wrong while processing your message. Please try again."

        for chunk in _split_message(reply):
            await message.answer(chunk, parse_mode="Markdown")

    # -- Text messages --------------------------------------------------

    @router.message()
    async def handle_message(message: types.Message) -> None:
        """Route text messages through the agent loop."""
        if not message.text:
            await message.answer(
                "I can only process text and voice messages. "
                "Please send a text or record a voice note 🎙️"
            )
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
            await message.answer(chunk, parse_mode="Markdown")

    return router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MARKDOWN_SPECIAL = r"\_*[]()~`>#+-=|{}.!"


def _escape_markdown(text: str) -> str:
    """Escape Telegram Markdown v1 special characters.

    Args:
        text: Raw text that may contain special chars.

    Returns:
        Escaped text safe for ``parse_mode="Markdown"``.
    """
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


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
