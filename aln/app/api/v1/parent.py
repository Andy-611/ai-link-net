"""Parent resource API - manage parent relationship."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from loguru import logger

from aln.app.misc import normalize_parent_url
from aln.app.misc.provider import get_host_runtime
from aln.app.schemas import StandardResponse
from aln.app.service import HostClient, HostClientError
from fp import Host, HostWellKnown

router = APIRouter(prefix="/parent", tags=["parent"])


@router.get(
    "", response_model=StandardResponse[HostWellKnown | None], summary="Get parent info"
)
def get_parent(
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[HostWellKnown | None]:
    """Return current parent's wellknown information."""
    if current_host.parent_host is None:
        return StandardResponse[HostWellKnown | None](
            success=True,
            message="Parent host is not set",
            data=None,
        )

    #NOTE: return 要用 StandardResponse 进行包装,保证接口干净，data 尽量用现有的 schema,不要随意定义 schema，如果现有的 schema 不满足需求，和我讨论新的 schema 定义
    return StandardResponse[HostWellKnown | None](
        success=True,
        message="Parent information retrieved",
        data=current_host.parent_host.get_wellknown(),
    )


@router.post(
    "",
    response_model=StandardResponse[HostWellKnown],
    summary="Set parent URL and register",
)
async def set_parent(
    parent_url: Annotated[str, Body(..., embed=True)],
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[HostWellKnown]:
    """Set parent URL, register on parent, and trigger reconnect."""
    parent_url = normalize_parent_url(parent_url)

    old_parent_url = current_host.parent_url
    old_parent_uid = current_host.parent_host.uid if current_host.parent_host else None

    hostclient = HostClient(parent_url, timeout=5.0)

    try:
        target_parent = hostclient.get_wellknown()
    except HostClientError as exc:
        logger.error(f"Failed to fetch parent wellknown from {parent_url}: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch parent wellknown from {parent_url}: {exc}",
        ) from exc

    if target_parent.uid == current_host.uid:
        raise HTTPException(
            status_code=400,
            detail=(
                "Parent host cannot be self: "
                f"current_uid={current_host.uid}, parent_uid={target_parent.uid}, "
                f"parent_url={parent_url}"
            ),
        )

    # Unregister from old parent if switching to a different one
    is_switching_parent = (
        old_parent_url
        and old_parent_uid
        and old_parent_uid != target_parent.uid
    )
    if is_switching_parent:
        try:
            old_client = HostClient(old_parent_url, timeout=5.0)
            old_client.unregister_child(current_host.uid)
            logger.info("Unregistered from old parent: url={}", old_parent_url)
        except Exception as exc:
            logger.warning(
                "Failed to unregister from old parent (url={}): {}",
                old_parent_url,
                exc,
            )
        await current_host.disconnect_from_parent()

    try:
        current_wellknown = current_host.get_wellknown()
        parent_wellknown = hostclient.register_child(current_wellknown)
    except HostClientError as exc:
        logger.error(
            "Failed to register child on parent: child_uid={}, parent_url={}, error={}",
            current_host.uid,
            parent_url,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to register child on parent: "
                f"child_uid={current_host.uid}, parent_url={parent_url}, error={exc}"
            ),
        ) from exc

    current_host.parent_url = parent_url
    current_host.save_parent_info(parent_wellknown)
    await current_host.ensure_parent_connection()

    # Persist host state
    current_host.save()

    return StandardResponse[HostWellKnown](
        success=True,
        message="Parent set successfully",
        data=parent_wellknown,
    )
