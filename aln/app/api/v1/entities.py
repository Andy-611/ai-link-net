"""Entity resource API - manage entities on this host."""

from __future__ import annotations

import inspect
import mimetypes
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from loguru import logger
from pydantic import BaseModel, Field

from fp import Entity, EntityCard, EntityStatus, Host
from fp.handler import HandlerConfig
from fp.utils.storage import get_storage_manager
from aln.app.schemas import StandardResponse, EntityUpdateRequest, RegisterEntityRequest
from aln.app.schemas.entity import BatchRegisterRequest
from aln.app.misc.exception_handler import exception_wrapper
from aln.app.misc.provider import get_target_entity, get_host_runtime

router = APIRouter(prefix="/entities", tags=["entities"])


def _with_avatar(card: EntityCard) -> EntityCard:
    """Enrich EntityCard with has_avatar flag by checking storage."""
    storage = get_storage_manager()
    return card.model_copy(update={"has_avatar": storage.get_entity_avatar_url(card.entity_uid) is not None})


async def _sync_parent_wellknown(current_host: Host) -> None:
    """Sync current host wellknown to parent when runtime supports it."""
    sync_fn = getattr(current_host, "sync_wellknown_to_parent", None)
    if not callable(sync_fn):
        return

    result = sync_fn()
    if inspect.isawaitable(result):
        await result


@router.post("", response_model=StandardResponse[EntityCard])
@exception_wrapper(catch_http_exc=True)
async def register_entity(
    request_data: RegisterEntityRequest,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[EntityCard]:
    """Register a new entity on this host."""
    try:
        if request_data.provider and request_data.kind.lower() != "agent":
            raise HTTPException(
                status_code=400,
                detail="provider can only be set when kind=agent",
            )

        metadata = dict(request_data.metadata)
        if request_data.provider:
            metadata["provider"] = request_data.provider

        # Build handler config from request (protocol layer)
        from fp.handler import TrustLevel, InteractionMode

        handler_config = HandlerConfig(
            trust_level=TrustLevel(request_data.trust_level),
            workdir=request_data.workdir,
            allowed_tools=request_data.allowed_tools,
            timeout=request_data.timeout,
            max_budget_usd=request_data.max_budget_usd,
            interaction_mode=InteractionMode(request_data.interaction_mode),
            stream_output=request_data.stream_output,
            output_format=request_data.output_format,
            model=request_data.model,
        )

        # Generate entity_uid as default name if not provided
        from uuid import uuid4
        entity_name = request_data.name or uuid4().hex[:8]

        # Register entity
        entity = current_host.register_entity(
            name=entity_name,
            kind=request_data.kind,
            is_public=request_data.is_public,
            description=request_data.description,
            metadata=metadata,
            provider=request_data.provider,
            handler_config=handler_config,
        )

        await _sync_parent_wellknown(current_host)

        return StandardResponse[EntityCard](
            success=True,
            message="Entity registered successfully",
            data=_with_avatar(entity.entity_card),
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Failed to register entity: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to register entity: {e}")
        raise HTTPException(status_code=500, detail="Failed to register entity") from e


@router.post("/batch", response_model=StandardResponse[list[EntityCard]])
@exception_wrapper(catch_http_exc=True)
async def register_entity_batch(
    request_data: BatchRegisterRequest,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[list[EntityCard]]:
    """Batch register multiple entities as an organization."""
    from uuid import uuid4

    from fp.handler import HandlerConfig, InteractionMode, TrustLevel

    org_id = uuid4().hex[:8]
    registered: list[Entity] = []

    for member in request_data.members:
        metadata: dict[str, Any] = {
            "organization": request_data.organization_name,
            "organization_id": org_id,
        }
        if member.provider:
            metadata["provider"] = member.provider

        handler_config = HandlerConfig(
            trust_level=TrustLevel(member.trust_level),
            interaction_mode=InteractionMode.BATCH,
            model=member.model,
            workdir=member.workdir,
        )

        entity = current_host.register_entity(
            name=member.name,
            kind=member.kind,
            is_public=member.is_public,
            description=member.description,
            metadata=metadata,
            provider=member.provider,
            handler_config=handler_config,
        )
        registered.append(entity)

    if request_data.auto_friend and len(registered) > 1:
        for i, entity in enumerate(registered):
            for other in registered[i + 1:]:
                entity.add_friend(other.entity_card)
                other.add_friend(entity.entity_card)

    current_host.save()

    await _sync_parent_wellknown(current_host)

    cards = [_with_avatar(e.entity_card) for e in registered]
    return StandardResponse[list[EntityCard]](
        success=True,
        message=f"Organization '{request_data.organization_name}' created with {len(cards)} members",
        data=cards,
    )


@router.get("", response_model=StandardResponse[list[EntityCard]])
async def list_entities(
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[list[EntityCard]]:
    """List all entities on this host."""
    entity_cards = [_with_avatar(entity.entity_card) for entity in current_host.entities.values()]

    return StandardResponse[list[EntityCard]](
        success=True,
        message="Entities list retrieved",
        data=entity_cards,
    )


@router.get("/discover", response_model=StandardResponse[list[EntityCard]])
@exception_wrapper(catch_http_exc=True)
async def discover_entities(
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[list[EntityCard]]:
    """Discover entities from self+children and one-level parent."""
    discover_fn = getattr(current_host, "get_discoverable_entities_from_network", None)
    if callable(discover_fn):
        discovered = discover_fn()
        entity_cards = await discovered if inspect.isawaitable(discovered) else discovered
    else:
        entity_cards = current_host.get_discoverable_entities(include_parent=True)

    return StandardResponse[list[EntityCard]](
        success=True,
        message="Discoverable entities retrieved",
        data=[_with_avatar(c) for c in entity_cards],
    )


@router.get("/card/{address}", response_model=StandardResponse[EntityCard])
@exception_wrapper(catch_http_exc=True)
async def get_entity_card_by_address(
    address: str,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[EntityCard]:
    """Get entity card by full address (host_uid:entity_uid).

    Searches in order:
    1. Local entities on this host
    2. Child hosts
    3. Parent host (if configured)
    """
    from fp import FPAddress

    try:
        fp_address = FPAddress(address=address)
        target_host_uid = fp_address.host_uid
        target_entity_uid = fp_address.entity_uid

        # 1. Check local entities
        if target_host_uid == current_host.uid:
            entity = current_host.get_entity(target_entity_uid)
            if entity:
                return StandardResponse[EntityCard](
                    success=True,
                    message="Entity card retrieved (local)",
                    data=_with_avatar(entity.entity_card),
                )

        # 2. Check child hosts
        if target_host_uid in current_host.child_hosts:
            child_host = current_host.child_hosts[target_host_uid]
            for entity_card in child_host.public_entities:
                if entity_card.entity_uid == target_entity_uid:
                    return StandardResponse[EntityCard](
                        success=True,
                        message="Entity card retrieved (child)",
                        data=entity_card,
                    )

        # 3. Check parent host (via network call)
        if hasattr(current_host, 'parent_url') and current_host.parent_url:
            from aln.app.service import HostClient
            try:
                parent_client = HostClient(current_host.parent_url, timeout=5.0)
                entities = parent_client.entity_search(address=address)
                if entities:
                    return StandardResponse[EntityCard](
                        success=True,
                        message="Entity card retrieved (parent)",
                        data=entities[0],
                    )
            except Exception as e:
                logger.warning(f"Failed to query parent for entity card: {e}")

        raise HTTPException(status_code=404, detail=f"Entity not found: {address}")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid address format: {e}")


@router.get("/{entity_uid}", response_model=StandardResponse[EntityCard])
async def get_entity(
    entity_uid: str,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[EntityCard]:
    """Get information about a specific entity on this host."""
    entity = current_host.get_entity(entity_uid)

    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_uid}")

    return StandardResponse[EntityCard](
        success=True,
        message="Entity information retrieved",
        data=_with_avatar(entity.entity_card),
    )


@router.get("/{entity_uid}/friends", response_model=StandardResponse[list[EntityCard]])
async def list_entity_friends(
    entity_uid: str,
    target_entity: Annotated[Entity, Depends(get_target_entity)],
) -> StandardResponse[list[EntityCard]]:
    """List all friends for one entity."""
    friends = [_with_avatar(card) for card in target_entity.friends.values()]
    return StandardResponse[list[EntityCard]](
        success=True,
        message=f"Friends list retrieved for entity: {entity_uid}",
        data=friends,
    )


class FriendStatus(BaseModel):
    """Friend online status."""
    entity_uid: str
    name: str
    address: str
    status: str  # "online" | "offline" | "deleted" | "unknown"


@router.get("/{entity_uid}/friends/status", response_model=StandardResponse[list[FriendStatus]])
async def get_friends_status(
    entity_uid: str,
    target_entity: Annotated[Entity, Depends(get_target_entity)],
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[list[FriendStatus]]:
    """Get online status for all friends of an entity."""
    friends_status = []

    for friend_card in target_entity.friends.values():
        # Determine status based on friend's location
        status_str = "unknown"

        # Check if friend is on the same host (local)
        if friend_card.host_uid == current_host.uid:
            # Local entities are always online
            status_str = "online"
        elif hasattr(current_host, 'entity_status'):
            # Check if current host has status info (if it's a parent host)
            entity_status = current_host.entity_status.get(friend_card.entity_uid)
            if entity_status:
                status_str = entity_status.value
            else:
                # Foreign entity but no status info available
                status_str = "unknown"

        friends_status.append(FriendStatus(
            entity_uid=friend_card.entity_uid,
            name=friend_card.name,
            address=friend_card.address.address,
            status=status_str,
        ))

    return StandardResponse[list[FriendStatus]](
        success=True,
        message=f"Friends status retrieved for entity: {entity_uid}",
        data=friends_status,
    )


@router.post("/{entity_uid}", response_model=StandardResponse[EntityCard])
@exception_wrapper(catch_http_exc=True)
async def update_entity(
    entity_uid: str,
    request_data: EntityUpdateRequest,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[EntityCard]:
    """Update entity settings (name, description, visibility, enabled state, metadata, etc)."""
    entity = current_host.update_entity(
        entity_uid=entity_uid,
        name=request_data.name,
        description=request_data.description,
        visible=request_data.visible,
        enabled=request_data.enabled,
        metadata=request_data.metadata,
    )
    await _sync_parent_wellknown(current_host)
    return StandardResponse[EntityCard](
        success=True,
        message="Entity updated successfully",
        data=_with_avatar(entity.entity_card),
    )


@router.delete("/{entity_uid}", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def delete_entity(
    entity_uid: str,
    # NOTE:所有的内容都放到调用 target_entity 和 current_host，交给 Entity 和 Host，符合 OOP 原则，不要在这里写过多的逻辑
    target_entity: Annotated[Entity, Depends(get_target_entity)],
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Delete an entity from this host."""
    try:
        # Delete entity
        current_host.delete_entity(entity_uid)
        await _sync_parent_wellknown(current_host)

        return StandardResponse[dict](
            success=True,
            message="Entity deleted successfully",
            data={},
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Failed to delete entity: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to delete entity: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete entity") from e


class MarkDeletedRequest(BaseModel):
    """Request to mark entity as deleted (from child host)."""
    host_uid: str = Field(..., description="Child host UID reporting the deletion")


@router.post("/{entity_uid}/mark_deleted", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def mark_entity_deleted(
    entity_uid: str,
    request_data: MarkDeletedRequest,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Mark entity as deleted (called by child host after deletion)."""
    # Verify child_uid belongs to a known child
    if request_data.host_uid not in current_host.child_hosts:
        raise HTTPException(
            status_code=403,
            detail=f"Host {request_data.host_uid} is not a registered child"
        )

    # Mark entity as DELETED and clear queue
    if hasattr(current_host, 'entity_status'):
        current_host.entity_status[entity_uid] = EntityStatus.DELETED
        current_host.offline_mail_queues.pop(entity_uid, None)
        logger.info(f"Entity {entity_uid} marked as DELETED by child {request_data.host_uid}")

    return StandardResponse[dict](
        success=True,
        message=f"Entity {entity_uid} marked as deleted",
        data={},
    )


# ============================================================================
# Avatar API
# ============================================================================

@router.get("/{entity_uid}/avatar")
@exception_wrapper(catch_http_exc=True)
async def get_entity_avatar(
    entity_uid: str,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> Response:
    """Get entity avatar image."""
    # Verify entity exists
    entity = current_host.get_entity(entity_uid)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_uid}")

    storage = get_storage_manager()
    result = storage.load_entity_avatar(entity_uid)

    if result is None:
        raise HTTPException(status_code=404, detail="Avatar not found")

    avatar_data, ext = result
    mime_type = mimetypes.types_map.get(f".{ext}", "image/png")

    return Response(content=avatar_data, media_type=mime_type)


@router.post("/{entity_uid}/avatar", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def upload_entity_avatar(
    entity_uid: str,
    file: UploadFile = File(...),
    current_host: Annotated[Host, Depends(get_host_runtime)] = None,
) -> StandardResponse[dict]:
    """Upload entity avatar image."""
    # Verify entity exists
    entity = current_host.get_entity(entity_uid)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_uid}")

    # Validate file type
    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image type: {file.content_type}. Allowed: {', '.join(allowed_types)}"
        )

    # Validate file size (max 5MB)
    max_size = 5 * 1024 * 1024  # 5MB
    data = await file.read()
    if len(data) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {len(data)} bytes (max {max_size} bytes)"
        )

    # Extract extension from filename or content_type
    if file.filename and "." in file.filename:
        ext = file.filename.split(".")[-1].lower()
    else:
        ext_map = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/gif": "gif",
            "image/webp": "webp",
        }
        ext = ext_map.get(file.content_type, "png")

    # Save avatar
    storage = get_storage_manager()
    storage.save_entity_avatar(entity_uid, data, ext)

    avatar_url = f"/api/v1/entities/{entity_uid}/avatar"

    return StandardResponse[dict](
        success=True,
        message="Avatar uploaded successfully",
        data={"avatar_url": avatar_url},
    )


@router.delete("/{entity_uid}/avatar", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def delete_entity_avatar(
    entity_uid: str,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Delete entity avatar image."""
    # Verify entity exists
    entity = current_host.get_entity(entity_uid)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_uid}")

    storage = get_storage_manager()
    deleted = storage.delete_entity_avatar(entity_uid)

    if not deleted:
        raise HTTPException(status_code=404, detail="Avatar not found")

    return StandardResponse[dict](
        success=True,
        message="Avatar deleted successfully",
        data={},
    )
