"""JSON-RPC 2.0 schemas.

Standard JSON-RPC 2.0 protocol schemas for request/response/error handling.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request."""

    jsonrpc: str = Field(default="2.0")
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error."""

    code: int
    message: str
    data: Any = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response."""

    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: Any = None
    error: JSONRPCError | None = None


class RPCErrorCode:
    """JSON-RPC 2.0 standard error codes."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
