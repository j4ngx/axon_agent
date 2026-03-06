"""Telegram bot initialisation and polling entry point.

This module wires up the aiogram ``Bot`` and ``Dispatcher`` and starts
long-polling.  It knows nothing about message handling — that lives in
``handlers.py``.
"""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, Router

logger = logging.getLogger(__name__)


def create_bot(token: str) -> Bot:
    """Create an aiogram ``Bot`` instance.

    Args:
        token: The Telegram bot token from BotFather.

    Returns:
        A configured ``Bot``.
    """
    return Bot(token=token)


def create_dispatcher(router: Router) -> Dispatcher:
    """Create an aiogram ``Dispatcher`` and attach the given router.

    Args:
        router: The router that contains all message handlers.

    Returns:
        A configured ``Dispatcher``.
    """
    dp = Dispatcher()
    dp.include_router(router)
    return dp


async def start_polling(bot: Bot, dispatcher: Dispatcher) -> None:
    """Start long-polling and block until shutdown.

    Args:
        bot: The aiogram ``Bot``.
        dispatcher: The aiogram ``Dispatcher`` with handlers registered.
    """
    logger.info("Axon Telegram bot starting long-polling…")
    try:
        await dispatcher.start_polling(bot, handle_signals=True)
    finally:
        await bot.session.close()
        logger.info("Axon Telegram bot stopped")
