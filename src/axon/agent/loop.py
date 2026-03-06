"""Core agent loop.

For every incoming user message the loop:

1. Persists the user message.
2. Loads recent conversation history.
3. Builds a system prompt that describes Axon and its available tools.
4. Iterates (up to ``max_iterations``):
   a. Calls the LLM.
   b. If the LLM requests a tool call → executes it and feeds the result back.
   c. If the LLM produces a final text answer → breaks.
5. Persists the assistant reply and returns it.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from axon.agent.context import AgentContext
from axon.config.settings import Settings
from axon.exceptions import LLMError, ToolError
from axon.llm.base import LLMClient, LLMResponse
from axon.memory.repositories import ChatHistoryRepository
from axon.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_FALLBACK_SYSTEM_PROMPT = "You are Axon, a helpful personal AI assistant. Be concise and accurate."

_FALLBACK_RESPONSE = (
    "I'm sorry, I wasn't able to produce a response after several attempts. "
    "Please try again or rephrase your question."
)


class AgentLoop:
    """Orchestrates a single reasoning cycle per user message.

    Args:
        llm: The LLM client (usually a :class:`~axon.llm.FallbackLLMClient`).
        memory: The chat history repository.
        tools: The tool registry.
        settings: Application settings.
    """

    def __init__(
        self,
        llm: LLMClient,
        memory: ChatHistoryRepository,
        tools: ToolRegistry,
        settings: Settings,
    ) -> None:
        self._llm = llm
        self._memory = memory
        self._tools = tools
        self._max_iterations = settings.agent.max_iterations
        self._history_limit = settings.agent.history_limit
        self._system_prompt_template = settings.agent.load_system_prompt()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self, user_id: int, user_message: str) -> str:
        """Process a user message and return the assistant's final reply.

        Args:
            user_id: Telegram user ID.
            user_message: The raw text the user sent.

        Returns:
            The assistant's textual reply to send back via Telegram.
        """
        # 1. Persist the incoming message.
        await self._memory.save_message(user_id=user_id, role="user", content=user_message)

        # 2. Build the initial context.
        context = await self._build_context(user_id)

        # 3. Iterate: think → (optional) act → observe → repeat.
        for iteration in range(1, self._max_iterations + 1):
            logger.info(
                "Agent iteration",
                extra={"user_id": user_id, "iteration": iteration},
            )

            try:
                response = await self._call_llm(context)
            except LLMError:
                logger.exception("LLM call failed during agent loop")
                return _FALLBACK_RESPONSE

            # If the LLM wants to use tools, execute them and continue.
            if response.tool_calls:
                await self._handle_tool_calls(context, response)
                continue

            # Otherwise we have a final textual answer.
            answer = response.content or _FALLBACK_RESPONSE
            await self._memory.save_message(user_id=user_id, role="assistant", content=answer)
            return answer

        # Safety net: max iterations exceeded.
        logger.warning(
            "Agent loop hit max iterations",
            extra={"user_id": user_id, "max": self._max_iterations},
        )
        await self._memory.save_message(
            user_id=user_id, role="assistant", content=_FALLBACK_RESPONSE
        )
        return _FALLBACK_RESPONSE

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _build_context(self, user_id: int) -> AgentContext:
        """Load history and build the initial message list."""
        history = await self._memory.get_recent_history(user_id, limit=self._history_limit)

        tools_desc = "\n".join(f"- **{t.name}**: {t.description}" for t in self._tools.list_tools())
        system_prompt = self._system_prompt_template.format(
            current_time=datetime.now(UTC).isoformat(),
            tools_description=tools_desc or "(none)",
        )

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        return AgentContext(
            user_id=user_id,
            messages=messages,
            max_iterations=self._max_iterations,
        )

    async def _call_llm(self, context: AgentContext) -> LLMResponse:
        """Send the current context to the LLM."""
        tools_schema = self._tools.get_openai_tools_schema() or None
        return await self._llm.generate(context.messages, tools=tools_schema)

    async def _handle_tool_calls(
        self,
        context: AgentContext,
        response: LLMResponse,
    ) -> None:
        """Execute requested tools and append results to the context."""
        # First, add the assistant message (with tool_calls metadata) to context.
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": response.content or ""}
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                },
            }
            for tc in response.tool_calls
        ]
        context.messages.append(assistant_msg)

        # Execute each tool and add the result as a tool message.
        for tc in response.tool_calls:
            tool = self._tools.get(tc.name)
            if tool is None:
                result = f"Error: unknown tool '{tc.name}'"
                logger.warning("Unknown tool requested", extra={"tool": tc.name})
            else:
                try:
                    logger.info("Executing tool", extra={"tool": tc.name, "args": tc.arguments})
                    result = await tool.run(**tc.arguments)
                except ToolError as exc:
                    result = f"Tool error: {exc}"
                    logger.error(
                        "Tool execution failed", extra={"tool": tc.name, "error": str(exc)}
                    )
                except Exception as exc:
                    result = f"Tool error: {exc}"
                    logger.exception("Unexpected tool error", extra={"tool": tc.name})

            context.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )
