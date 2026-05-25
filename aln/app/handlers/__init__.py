"""Application-layer handler implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from aln.app.adapters.cli_adapter import CLIAdapter
from fp.core.base import EntityKind
from fp.handler import BaseHandler, HandlerConfig

from .a2a_handler import A2AHandler
from .agent_handler import AgentHandler, build_agent_system_prompt
from .human_handler import HumanHandler
from .mcp_handler import MCPHandler

if TYPE_CHECKING:
    from fp.entity import Entity


def create_cli_adapter(provider: str | None) -> CLIAdapter | None:
    """Create CLI adapter for provider."""
    if provider is None:
        return None

    normalized = provider.strip().lower()
    if not normalized:
        return None

    try:
        return CLIAdapter(normalized)
    except (ValueError, FileNotFoundError):
        logger.warning(f"Unknown AGENT provider '{normalized}'")
        return None


def create_entity_handler(
    entity: Entity,
    kind: EntityKind | str,
    *,
    provider: str | None = None,
    system_prompt: str | None = None,
    handler_config: HandlerConfig | dict[str, Any] | None = None,
) -> BaseHandler:
    """Create default handler by entity kind with optional provider."""
    kind_value = kind.value if isinstance(kind, EntityKind) else str(kind).lower()

    if kind_value == EntityKind.HUMAN.value:
        return HumanHandler(entity)

    if kind_value in {
        EntityKind.TOOL.value,
        EntityKind.RESOURCE.value,
        EntityKind.SERVICE.value,
    }:
        return MCPHandler(entity)

    if kind_value == EntityKind.AGENT.value and entity.metadata.get("a2a_config"):
        return A2AHandler(entity)

    if isinstance(handler_config, HandlerConfig):
        config = handler_config
    elif isinstance(handler_config, dict):
        config = HandlerConfig.from_dict(handler_config)
    else:
        config = HandlerConfig()

    if kind_value != EntityKind.AGENT.value:
        logger.warning(f"Unknown entity kind '{kind_value}', fallback to AgentHandler")

    return AgentHandler(entity, provider=provider, config=config)


__all__ = [
    "A2AHandler",
    "AgentHandler",
    "CLIAdapter",
    "HumanHandler",
    "MCPHandler",
    "build_agent_system_prompt",
    "create_cli_adapter",
    "create_entity_handler",
]
