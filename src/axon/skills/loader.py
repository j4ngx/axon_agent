"""Skill loader — reads skill declarations from config and registers tools.

Supports two skill types:

- **builtin** — Python classes under ``axon/tools/`` discovered by name.
- **mcp** — External MCP servers connected via stdio transport.
"""

from __future__ import annotations

import logging

from axon.config.settings import SkillConfig
from axon.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Registry mapping builtin skill names -> their tool classes.
_BUILTIN_SKILLS: dict[str, type] = {}


def _discover_builtins() -> None:
    """Populate ``_BUILTIN_SKILLS`` with known builtin tool classes."""
    if _BUILTIN_SKILLS:
        return

    from axon.tools.get_current_time import GetCurrentTimeTool
    from axon.tools.gog import GogGmailTool, GogCalendarTool, GogSheetsTool


    # Add new builtins here:
    for cls in [GetCurrentTimeTool, GogGmailTool, GogCalendarTool, GogSheetsTool]:

        instance = cls()
        _BUILTIN_SKILLS[instance.name] = cls


async def load_skills(
    registry: ToolRegistry,
    skill_configs: list[SkillConfig],
) -> None:
    """Load and register all enabled skills declared in config.

    Args:
        registry: The tool registry to populate.
        skill_configs: Skill declarations from ``config.yml``.
    """
    _discover_builtins()

    for skill in skill_configs:
        if not skill.enabled:
            logger.debug("Skipping disabled skill", extra={"skill": skill.name})
            continue

        if skill.type == "builtin":
            await _load_builtin(registry, skill)
        elif skill.type == "mcp":
            await _load_mcp(registry, skill)
        else:
            logger.warning(
                "Unknown skill type — skipping",
                extra={"skill": skill.name, "type": skill.type},
            )


async def _load_builtin(registry: ToolRegistry, skill: SkillConfig) -> None:
    """Register a builtin tool by name."""
    cls = _BUILTIN_SKILLS.get(skill.name)
    if cls is None:
        logger.warning("Builtin skill not found — skipping", extra={"skill": skill.name})
        return
    registry.register(cls())
    logger.info("Loaded builtin skill", extra={"skill": skill.name})


async def _load_mcp(registry: ToolRegistry, skill: SkillConfig) -> None:
    """Connect to an MCP server and register its tools.

    Requires the ``mcp`` package (install with ``uv sync --extra mcp``).
    If not installed, the skill is skipped with a warning so the rest of
    Axon still works.
    """
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        logger.warning(
            "MCP skill '%s' skipped — install 'mcp' package: uv sync --extra mcp",
            skill.name,
        )
        return

    from axon.skills.mcp_adapter import MCPToolAdapter

    if skill.transport != "stdio":
        logger.warning(
            "Unsupported MCP transport '%s' for skill '%s' — only 'stdio' supported",
            skill.transport,
            skill.name,
        )
        return

    if not skill.command:
        logger.error("MCP skill '%s' missing 'command' field", skill.name)
        return

    server_params = StdioServerParameters(
        command=skill.command,
        args=skill.args,
        env=skill.env or None,
    )

    try:
        read_stream, write_stream = await stdio_client(server_params).__aenter__()
        session = ClientSession(read_stream, write_stream)
        await session.__aenter__()
        await session.initialize()

        tools_result = await session.list_tools()
        for mcp_tool in tools_result.tools:
            adapter = MCPToolAdapter(
                session=session,
                mcp_tool=mcp_tool,
                skill_name=skill.name,
            )
            registry.register(adapter)

        # Track session so it can be closed on shutdown.
        registry.add_mcp_session(session)

        logger.info(
            "Loaded MCP skill",
            extra={"skill": skill.name, "tools": [t.name for t in tools_result.tools]},
        )
    except Exception:
        logger.exception("Failed to load MCP skill '%s'", skill.name)
