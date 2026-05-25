"""Common utility functions."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from fp import Entity, Host


def now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def resolve_sender_entity(host: Host, identifier: str) -> Entity:
    """Resolve sender by uid first, then by exact name."""
    entity = host.get_entity(identifier)
    if entity is not None:
        return entity
    matches = [e for e in host.entities.values() if e.name == identifier]
    if not matches:
        raise HTTPException(status_code=404, detail=f"Entity not found: {identifier}")
    if len(matches) > 1:
        raise HTTPException(status_code=400, detail=f"Ambiguous entity name: {identifier}")
    return matches[0]
