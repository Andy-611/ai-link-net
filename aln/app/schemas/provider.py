"""Provider-related schemas for API requests and responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ProviderCheckRequest(BaseModel):
    """Check provider availability request."""

    provider: Literal["claude", "codex", "autowork", "openclaw", "hermes"]


class ProviderCheckResponse(BaseModel):
    """Provider availability check response."""

    available: bool
    provider: str
    version: str | None = None
    executable_path: str | None = None
    error: str | None = None
