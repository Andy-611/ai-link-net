"""Friend API - send friend requests via Entity.send_message."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from fp import Entity, FPAddress, Host, Message, MessageKind
from fp.message import FriendRequestPayload

from aln.app.misc.common import resolve_sender_entity
from aln.app.misc.exception_handler import exception_wrapper
from aln.app.misc.provider import get_host_runtime
from aln.app.schemas import StandardResponse

router = APIRouter(prefix="/friends", tags=["friends"])


class FriendAddRequest(BaseModel):
    """Friend add request payload."""

    from_entity: str
    to_address: str
    text: str | None = None


class FriendDeleteRequest(BaseModel):
    """Friend delete request payload."""

    from_entity: str
    friend_uid: str


@router.post("/add", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def add_friend(
    request_data: FriendAddRequest,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Send friend request from one local entity to target address."""
    sender_entity = resolve_sender_entity(current_host, request_data.from_entity)
    recipient_address = FPAddress(address=request_data.to_address)
    request_text = (
        request_data.text
        if request_data.text is not None
        else f"{sender_entity.name} wants to add you as a friend"
    )
    friend_request_message = Message(
        kind=MessageKind.FRIEND_REQUEST,
        payload=FriendRequestPayload(
            sender_card=sender_entity.entity_card,
            text=request_text,
        ),
    )
    mail = await sender_entity.send_message(
        to=recipient_address,
        message=friend_request_message,
    )
    return StandardResponse[dict](
        success=True,
        message="Friend request delivered to recipient mailbox",
        data={
            "message_id": mail.message.message_id,
            "from_entity_uid": sender_entity.uid,
            "to_address": request_data.to_address,
        },
    )


@router.post("/delete", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def delete_friend(
    request_data: FriendDeleteRequest,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Remove a friend from one local entity's friend list (one-sided)."""
    entity = resolve_sender_entity(current_host, request_data.from_entity)

    friend_uid = request_data.friend_uid
    if friend_uid not in entity.friends:
        raise HTTPException(
            status_code=404,
            detail=f"Friend not found: {friend_uid}",
        )

    friend_name = entity.friends[friend_uid].name
    entity.remove_friend(friend_uid)
    entity.save()

    return StandardResponse[dict](
        success=True,
        message=f"Friend '{friend_name}' removed successfully",
        data={
            "from_entity_uid": entity.uid,
            "removed_friend_uid": friend_uid,
            "removed_friend_name": friend_name,
        },
    )
