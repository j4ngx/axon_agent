"""Axon entry point — thin orchestrator that delegates to the DI container.

Responsibilities (and nothing else):

1. Load configuration (YAML + env secrets).
2. Initialise logging.
3. Build the DI container (wires everything together).
4. Start the Telegram long-polling loop.
5. Gracefully shut down on exit.
"""

from __future__ import annotations

import asyncio
import logging

from axon.config.settings import Settings
from axon.di.container import Container
from axon.logging.setup import setup_logging
from axon.telegram.bot import start_polling

logger = logging.getLogger(__name__)


async def async_main() -> None:
    """Async entry point — build the object graph and start polling."""
    # 1. Configuration
    settings = Settings.from_yaml()

    # 2. Logging
    setup_logging(level=settings.logging.level)
    logger.info("Axon starting", extra={"version": "0.1.0"})

    # 3. DI container
    container = Container(settings)
    await container.init()

    # 4. Telegram long-polling
    try:
        logger.info(
            "Axon ready — listening for Telegram messages",
            extra={"allowed_users": settings.telegram_allowed_user_ids},
        )
        await start_polling(container.bot, container.dispatcher)
    finally:
        # 5. Graceful shutdown
        await container.shutdown()


def run() -> None:
    """Synchronous wrapper — the project script entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Axon shut down by user")


if __name__ == "__main__":
    run()
