"""Health routes for host app."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from fp import Host
from aln.app.misc.provider import get_host_runtime
from aln.app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Host health check")
def health(current_host: Host = Depends(get_host_runtime)) -> HealthResponse:
    """Return host process liveness and host name."""
    return HealthResponse(host_name=current_host.name)
