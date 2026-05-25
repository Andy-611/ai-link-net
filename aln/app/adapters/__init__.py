"""Provider adapters for application-layer agent entities."""

from .a2a_client import (
    A2AAgentCard,
    A2AAgentConfig,
    A2AClient,
    A2AInterface,
    A2AMessageResult,
    A2ASkill,
    HttpA2AClient,
    create_a2a_client,
)
from .cli_adapter import CLIAdapter, CLIResult
from .mcp_client import MCPClient, MCPEntityConfig, MCPToolResult, create_mcp_client
from .prompts import AGENT_HANDLER_PROMPT_TEMPLATE

__all__ = [
    "AGENT_HANDLER_PROMPT_TEMPLATE",
    "A2AAgentCard",
    "A2AAgentConfig",
    "A2AClient",
    "A2AInterface",
    "A2AMessageResult",
    "A2ASkill",
    "CLIAdapter",
    "CLIResult",
    "HttpA2AClient",
    "MCPClient",
    "MCPEntityConfig",
    "MCPToolResult",
    "create_a2a_client",
    "create_mcp_client",
]
