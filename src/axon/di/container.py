"""Lightweight dependency-injection container.

Axon uses **explicit constructor injection** — every component declares its
dependencies as constructor arguments.  The ``Container`` builds the full
object graph once at startup and exposes each service as a property.

Why a hand-rolled container instead of a framework?

* Zero magic — easy to understand, debug, and test.
* No decorators / metaclasses / module-level side-effects.
* The object graph is small and unlikely to grow into hundreds of services.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from axon.agent.loop import AgentLoop
from axon.config.settings import Settings
from axon.llm.fallback import FallbackLLMClient
from axon.llm.groq_client import GroqLLMClient
from axon.llm.openrouter_client import OpenRouterLLMClient
from axon.memory.db import create_engine, create_session_factory, init_db
from axon.memory.repositories import ChatHistoryRepository
from axon.skills.loader import load_skills
from axon.telegram.bot import create_bot, create_dispatcher
from axon.telegram.handlers import create_router
from axon.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from aiogram import Bot, Dispatcher
    from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

logger = logging.getLogger(__name__)


class Container:
    """Application-level service container.

    Instantiate with a ``Settings`` object, call ``await container.init()``
    to build the async parts (DB, MCP connections, …), then access services
    via properties.

    Args:
        settings: The root ``Settings`` instance.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

        # Lazy — populated by ``init()``.
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker | None = None
        self._memory: ChatHistoryRepository | None = None
        self._llm: FallbackLLMClient | None = None
        self._tools: ToolRegistry | None = None
        self._agent: AgentLoop | None = None
        self._bot: Bot | None = None
        self._dispatcher: Dispatcher | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def init(self) -> None:
        """Build the full service graph (async-safe).

        Must be called exactly once before accessing any property.
        """
        logger.info("Initialising DI container")

        # 1. Persistence
        self._engine = create_engine(self._settings.memory.db_path)
        await init_db(self._engine)
        self._session_factory = create_session_factory(self._engine)
        self._memory = ChatHistoryRepository(self._session_factory)

        # 2. LLM clients
        groq = GroqLLMClient(
            api_key=self._settings.groq_api_key,
            model=self._settings.llm.groq.model,
            timeout=self._settings.llm.groq.timeout,
        )
        openrouter = OpenRouterLLMClient(
            api_key=self._settings.openrouter_api_key,
            model=self._settings.llm.openrouter.model,
            timeout=self._settings.llm.openrouter.timeout,
        )
        self._llm = FallbackLLMClient(primary=groq, fallback=openrouter)

        # 3. Tools — builtin + skills (MCP, etc.)
        self._tools = ToolRegistry()
        await load_skills(
            registry=self._tools,
            skill_configs=self._settings.skills,
        )

        # 4. Agent
        self._agent = AgentLoop(
            llm=self._llm,
            memory=self._memory,
            tools=self._tools,
            settings=self._settings,
        )

        # 5. Telegram
        self._bot = create_bot(token=self._settings.telegram_bot_token)
        router = create_router(
            agent_loop=self._agent,
            allowed_user_ids=self._settings.telegram_allowed_user_ids,
        )
        self._dispatcher = create_dispatcher(router)

        logger.info("DI container initialised — all services ready")

    async def shutdown(self) -> None:
        """Gracefully tear down resources."""
        logger.info("Shutting down DI container")
        if self._tools:
            await self._tools.shutdown()
        if self._engine:
            await self._engine.dispose()
        if self._bot:
            await self._bot.session.close()
        logger.info("DI container shut down")

    # ------------------------------------------------------------------
    # Service accessors
    # ------------------------------------------------------------------

    @property
    def settings(self) -> Settings:
        """Return the root settings."""
        return self._settings

    @property
    def memory(self) -> ChatHistoryRepository:
        """Return the chat history repository."""
        assert self._memory is not None, "Container not initialised"
        return self._memory

    @property
    def llm(self) -> FallbackLLMClient:
        """Return the LLM client with fallback."""
        assert self._llm is not None, "Container not initialised"
        return self._llm

    @property
    def tools(self) -> ToolRegistry:
        """Return the tool registry."""
        assert self._tools is not None, "Container not initialised"
        return self._tools

    @property
    def agent(self) -> AgentLoop:
        """Return the agent loop."""
        assert self._agent is not None, "Container not initialised"
        return self._agent

    @property
    def bot(self) -> Bot:
        """Return the Telegram bot."""
        assert self._bot is not None, "Container not initialised"
        return self._bot

    @property
    def dispatcher(self) -> Dispatcher:
        """Return the Telegram dispatcher."""
        assert self._dispatcher is not None, "Container not initialised"
        return self._dispatcher
