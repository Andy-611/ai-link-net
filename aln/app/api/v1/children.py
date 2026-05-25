"""Children resource API - manage child hosts (formerly peers)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from fp import EntityStatus, Host, HostWellKnown
from aln.app.misc.provider import get_host_runtime, get_market_store
from aln.app.schemas import StandardResponse
from aln.app.schemas.market import MarketStore

router = APIRouter(prefix="/children", tags=["children"])


class EntityStatusUpdate(BaseModel):
    """Entity status update request from child host."""
    status: str  # "online" or "offline"


@router.post("", response_model=StandardResponse[HostWellKnown])
def register_child(
    child_wellknown: HostWellKnown,
    host_server: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[HostWellKnown]:
    """Register a child host on this parent.

    Accepts the child's complete wellknown document as registration payload.
    """
    try:
        host_server.register_child(child_wellknown)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Child registration rejected: "
                f"uid={child_wellknown.uid}, name={child_wellknown.name}, reason={exc}"
            ),
        ) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected error when registering child uid={}, name={}",
            child_wellknown.uid,
            child_wellknown.name,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "Child registration failed unexpectedly: "
                f"uid={child_wellknown.uid}, name={child_wellknown.name}"
            ),
        ) from exc
    current_wellknown = host_server.get_wellknown()

    return StandardResponse[HostWellKnown](
        success=True,
        message="Child registered successfully",
        data=current_wellknown,
    )


@router.get("", response_model=StandardResponse[list[HostWellKnown]])
def list_children(
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[list[HostWellKnown]]:
    """List all registered child hosts."""
    children_list = [child.get_wellknown() for child in current_host.child_hosts.values()]
    return StandardResponse[list[HostWellKnown]](
        success=True,
        message="Children list retrieved",
        data=children_list,
    )


@router.get("/{child_uid}", response_model=StandardResponse[HostWellKnown])
def get_child(
    child_uid: str,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[HostWellKnown]:
    """Get information about a specific child host."""
    child_host = current_host.child_hosts.get(child_uid)

    if child_host is None:
        raise HTTPException(status_code=404, detail=f"Child not found: {child_uid}")

    return StandardResponse[HostWellKnown](
        success=True,
        message="Child information retrieved",
        data=child_host.get_wellknown(),
    )


@router.delete("/{child_uid}", response_model=StandardResponse[dict])
def delete_child(
    child_uid: str,
    current_host: Annotated[Host, Depends(get_host_runtime)],
    market_store: Annotated[MarketStore, Depends(get_market_store)],
) -> StandardResponse[dict]:
    """Remove a child host registration and clean up its market orders."""
    deleted = current_host.delete_host_by_uid(child_uid)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Child not found: {child_uid}")

    removed_orders = market_store.remove_orders_by_host_uid(child_uid)
    if removed_orders:
        market_store.save(current_host.uid)
        logger.info("Removed {} market orders from deleted child {}", removed_orders, child_uid)

    return StandardResponse[dict](
        success=True,
        message="Child removed successfully",
        data={},
    )


@router.post("/{child_uid}/entities/{entity_uid}/status", response_model=StandardResponse[dict])
async def update_entity_status(
    child_uid: str,
    entity_uid: str,
    status_update: EntityStatusUpdate,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Update entity online status (called by child host when entity connects/disconnects)."""
    from aln.app.service.host_server import HostServer

    if not isinstance(current_host, HostServer):
        raise HTTPException(status_code=500, detail="Host runtime does not support entity status")

    # Verify child exists
    if child_uid not in current_host.child_hosts:
        raise HTTPException(status_code=404, detail=f"Child not found: {child_uid}")

    # Update entity status
    try:
        new_status = EntityStatus(status_update.status.lower())
        current_host.entity_status[entity_uid] = new_status
        logger.info(f"Entity {entity_uid} status updated to {new_status.value} by child {child_uid}")

        if new_status == EntityStatus.ONLINE:
            await current_host.flush_offline_queue_for_entity(child_uid, entity_uid)

        return StandardResponse[dict](
            success=True,
            message=f"Entity status updated to {new_status.value}",
            data={"entity_uid": entity_uid, "status": new_status.value},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status_update.status}") from e
