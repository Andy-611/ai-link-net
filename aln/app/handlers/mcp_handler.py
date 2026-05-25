"""Handler for MCP-backed entities (tool/resource/service)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from aln.app.adapters.mcp_client import MCPClient, MCPEntityConfig, create_mcp_client
from aln.app.handlers._shared import extract_session_id, reply_invoke
from fp.handler import BaseHandler
from fp.message import Message, MessageKind

if TYPE_CHECKING:
    from fp.entity import Entity


class MCPHandler(BaseHandler):
    """Reads MCPEntityConfig from entity.metadata['mcp_config'],
    lazily creates an MCPClient, and forwards INVOKE messages as tool calls.
    """

    def __init__(self, entity: Entity) -> None:
        super().__init__(entity)
        self._client: MCPClient | None = None

    async def _ensure_client_ready(self) -> MCPClient:
        """Lazily init MCPClient; on first connect fetch and cache tool list."""
        if self._client is not None:
            return self._client

        raw = self.entity.metadata.get("mcp_config")
        if not raw:
            raise ValueError(f"Entity {self.entity.uid} missing 'mcp_config' in metadata")

        config = MCPEntityConfig.model_validate(raw)
        self._client = create_mcp_client(config)

        try:
            tools = await self._client.list_tools()
            self.entity.metadata["mcp_tools"] = tools
            logger.info(f"[MCPHandler] {self.entity.name}: loaded {len(tools)} tools")
        except Exception as e:
            logger.warning(f"[MCPHandler] Failed to fetch tool list: {e}")

        return self._client

    async def handle(self, message: Message) -> None:
        if message.kind != MessageKind.INVOKE:
            logger.warning(f"[MCPHandler] Ignoring non-INVOKE message: {message.kind}")
            return

        payload = message.payload
        tool_name: str | None = (
            getattr(payload, "method", None)
            or (payload.get("method") if isinstance(payload, dict) else None)
        )
        tool_params: dict[str, Any] = (
            getattr(payload, "params", None)
            or (payload.get("params") if isinstance(payload, dict) else None)
            or {}
        )

        if not tool_name:
            logger.warning("[MCPHandler] INVOKE payload missing 'method' (tool name)")
            return

        if tool_name == "mcp.list_tools":
            await self._handle_list_tools(message, payload)
            return

        try:
            client = await self._ensure_client_ready()
            result = await client.call_tool(tool_name, tool_params)
            logger.info(f"[MCPHandler] Tool '{tool_name}' returned {len(result.content)} content blocks")
            await reply_invoke(
                self.entity, message,
                text=result.text,
                session_id=extract_session_id(payload),
            )
        except Exception as e:
            logger.error(f"[MCPHandler] Tool call '{tool_name}' failed: {e}")

    async def _handle_list_tools(self, message: Message, payload: Any) -> None:
        await self._ensure_client_ready()
        tools = self.entity.metadata.get("mcp_tools", [])
        await reply_invoke(
            self.entity, message,
            text="",
            session_id=extract_session_id(payload),
            extra={"mcp_tools": tools},
        )
