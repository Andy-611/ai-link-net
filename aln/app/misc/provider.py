"""FastAPI dependency injection providers for common resources."""

from __future__ import annotations

from fastapi import HTTPException, Request

from fp import Entity

from aln.app.schemas.market import MarketStore
from aln.app.service import HostServer


async def get_host_runtime(request: Request) -> HostServer:
    """Get host runtime from app state."""
    host_runtime = getattr(request.app.state, "host_runtime", None)
    if host_runtime is None:
        raise HTTPException(status_code=500, detail="Host runtime not found")
    return host_runtime


async def get_market_store(request: Request) -> MarketStore:
    """Get market store from app state."""
    store = getattr(request.app.state, "market_store", None)
    if store is None:
        raise HTTPException(status_code=500, detail="Market store not initialized")
    return store


async def get_target_entity(request: Request, entity_uid: str) -> Entity:
    """Get entity from current host by entity_uid."""
    host_runtime = await get_host_runtime(request)
    entity = host_runtime.get_entity(entity_uid)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_uid}")
    return entity