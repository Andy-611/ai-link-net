"""Shared Pydantic schemas for common host API responses.

API-specific schemas should be defined in their respective API files:
- parent.py: ParentInfoResponse, SetParentRequest, SetParentResponse
- children.py: ChildRegisterRequest/Response, ChildInfo, ChildListResponse
- hosts.py: UpdateHostConfigRequest/Response
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    #NOTE:这里修改的时候，检查 src/cli/utils/cli_printer.py的print_status_report方法，同步修改
    """Health check response payload."""

    ok: bool = Field(default=True)
    service: str = Field(default="fp-host-server")
    host_name: str


class HostInfoResponse(BaseModel):
    """Host information response payload."""

    host_name: str
    uid: str
    public_key: str
    bind_host: str
    port: int
    entities: dict = Field(default_factory=dict)

class HostUpdateRequest(BaseModel):
    """Update host configuration request payload."""

    host_name: str = Field(..., description="Name of the host to update")
    parent_url: str | None = None
    bind_host: str | None = None
    port: int | None = None
    set_default: bool = False


class HostUpdateResponse(BaseModel):
    """Update host configuration response payload."""
    # TODO:这里不应该有 success 字段，应该包在 StandardResponse 里面，保持 API 响应格式一致。检查 app/endpoint.py 的 UPDATE_HOST_ENDPOINT 定义，确保返回类型正确。

    success: bool
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
