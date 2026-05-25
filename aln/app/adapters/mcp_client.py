"""MCP client adapter - connects FP entities to external MCP servers."""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Literal

from loguru import logger
from pydantic import BaseModel


class MCPEntityConfig(BaseModel):
    """Connection config stored in entity.metadata['mcp_config']."""

    transport: Literal["stdio", "http"]
    command: list[str] | None = None  # stdio: the process to spawn
    url: str | None = None  # http: the MCP server endpoint


class MCPToolResult(BaseModel):
    """Normalized result from an MCP tool call."""

    content: list[dict[str, Any]]
    is_error: bool = False

    @property
    def text(self) -> str:
        """Extract concatenated text from content blocks."""
        return "\n".join(
            item.get("text", "") for item in self.content if item.get("type") == "text"
        )


class MCPClient(ABC):
    """Abstract client that speaks MCP protocol to an external server."""

    @abstractmethod
    async def call_tool(self, name: str, params: dict[str, Any]) -> MCPToolResult:
        """Call a tool on the MCP server."""

    async def list_tools(self) -> list[dict[str, Any]]:
        """List tools exposed by the MCP server. TODO: implement in subclasses."""
        return []

    async def list_resources(self) -> list[dict[str, Any]]:
        """List resources exposed by the MCP server. TODO: implement in subclasses."""
        return []


class StdioMCPClient(MCPClient):
    """MCP client over STDIO transport — maintains a persistent subprocess."""

    def __init__(self, command: list[str]) -> None:
        self._command = command
        self._proc: asyncio.subprocess.Process | None = None
        self._msg_id: int = 0

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def _is_alive(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def _ensure_connected(self) -> None:
        """Spawn and initialize the MCP server process if not alive."""
        if self._is_alive():
            return

        logger.debug(f"[StdioMCPClient] Spawning: {self._command}")
        self._proc = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await self._send({
            "jsonrpc": "2.0", "id": self._next_id(), "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "aln-mcp-client", "version": "0.1"},
            },
        })
        await self._recv()  # discard initialize response
        await self._send({
            "jsonrpc": "2.0", "method": "notifications/initialized", "params": {},
        })
        logger.debug("[StdioMCPClient] Process ready")

    async def call_tool(self, name: str, params: dict[str, Any]) -> MCPToolResult:
        """Call a tool, reusing the persistent process (reconnects if dead)."""
        try:
            await self._ensure_connected()
            await self._send({
                "jsonrpc": "2.0", "id": self._next_id(), "method": "tools/call",
                "params": {"name": name, "arguments": params},
            })
            response = await self._recv()
        except Exception as e:
            logger.warning(f"[StdioMCPClient] Connection lost ({e}), reconnecting...")
            await self.close()
            await self._ensure_connected()
            await self._send({
                "jsonrpc": "2.0", "id": self._next_id(), "method": "tools/call",
                "params": {"name": name, "arguments": params},
            })
            response = await self._recv()

        result = response.get("result", {})
        return MCPToolResult(
            content=result.get("content", []),
            is_error=result.get("isError", False),
        )

    async def close(self) -> None:
        """Terminate the MCP server process."""
        if self._proc is None:
            return
        try:
            self._proc.stdin.close()
            await asyncio.wait_for(self._proc.wait(), timeout=3.0)
        except Exception:
            self._proc.kill()
        finally:
            self._proc = None
            logger.debug("[StdioMCPClient] Process closed")

    async def _send(self, msg: dict) -> None:
        self._proc.stdin.write((json.dumps(msg) + "\n").encode())
        await self._proc.stdin.drain()

    async def _recv(self) -> dict:
        line = await self._proc.stdout.readline()
        return json.loads(line) if line.strip() else {}

    async def list_tools(self) -> list[dict[str, Any]]:
        """Fetch tools/list from the MCP server."""
        await self._ensure_connected()
        await self._send({
            "jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list", "params": {},
        })
        response = await self._recv()
        return response.get("result", {}).get("tools", [])

    async def list_resources(self) -> list[dict[str, Any]]:
        """TODO: implement resources/list via STDIO."""
        return []


class HttpMCPClient(MCPClient):
    """MCP client over HTTP transport — POSTs JSON-RPC to a server URL."""

    def __init__(self, url: str) -> None:
        self._url = url.rstrip("/")

    async def call_tool(self, name: str, params: dict[str, Any]) -> MCPToolResult:
        """POST JSON-RPC tools/call to MCP server."""
        payload = {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": params},
        }
        response = await asyncio.to_thread(self._post, payload)
        result = response.get("result", {})
        return MCPToolResult(
            content=result.get("content", []),
            is_error=result.get("isError", False),
        )

    def _post(self, payload: dict) -> dict:
        """Blocking HTTP POST — runs in a thread via asyncio.to_thread."""
        import urllib.request

        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self._url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    async def list_tools(self) -> list[dict[str, Any]]:
        """Fetch tools/list from the MCP server via HTTP."""
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        response = await asyncio.to_thread(self._post, payload)
        return response.get("result", {}).get("tools", [])

    async def list_resources(self) -> list[dict[str, Any]]:
        """TODO: implement resources/list via HTTP."""
        return []


def create_mcp_client(config: MCPEntityConfig) -> MCPClient:
    """Factory: instantiate the right MCPClient from config."""
    if config.transport == "stdio":
        if not config.command:
            raise ValueError("stdio transport requires command")
        logger.debug(f"Creating StdioMCPClient: command={config.command}")
        return StdioMCPClient(config.command)

    if config.transport == "http":
        if not config.url:
            raise ValueError("http transport requires url")
        logger.debug(f"Creating HttpMCPClient: url={config.url}")
        return HttpMCPClient(config.url)

    raise ValueError(f"Unknown MCP transport: {config.transport}")
