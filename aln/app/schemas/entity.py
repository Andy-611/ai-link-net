"""Entity-related schemas for API requests and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RegisterEntityRequest(BaseModel):
    """Register entity request payload."""

    name: str | None = None
    kind: str
    provider: str | None = None
    description: str = ""
    is_public: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Agent runtime configuration (protocol layer)
    trust_level: Literal["untrusted", "semi_trusted", "fully_trusted"] = "fully_trusted"
    workdir: str | None = None
    allowed_tools: list[str] | None = None
    timeout: float = 600.0
    max_budget_usd: float | None = None
    interaction_mode: Literal["interactive", "batch"] = "batch"
    stream_output: bool = False
    output_format: Literal["text", "json", "stream-json"] = "json"
    model: str | None = None


class EntityUpdateRequest(BaseModel):
    """Update entity request payload."""

    name: str | None = None
    description: str | None = None
    visible: bool | None = None
    enabled: bool | None = None
    metadata: dict[str, Any] | None = None


class BatchMemberRequest(BaseModel):
    """Single member in a batch registration."""

    name: str
    kind: str = "agent"
    provider: str | None = None
    description: str = ""
    is_public: bool = True
    trust_level: Literal["untrusted", "semi_trusted", "fully_trusted"] = "fully_trusted"
    model: str | None = None
    workdir: str | None = None


class BatchRegisterRequest(BaseModel):
    """Batch register multiple entities as an organization."""

    organization_name: str
    members: list[BatchMemberRequest]
    auto_friend: bool = True

