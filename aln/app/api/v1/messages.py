"""Messages API - send text messages between entities."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from fp import FPAddress, Host, Mail, Message, MessageKind
from fp.mailbox import Mailbox
from fp.message import InvokePayload

from aln.app.misc.common import resolve_sender_entity
from aln.app.misc.exception_handler import exception_wrapper
from aln.app.misc.provider import get_host_runtime
from aln.app.schemas import StandardResponse
from aln.app.service import SessionService

router = APIRouter(prefix="/messages", tags=["messages"])


class SendMessageRequest(BaseModel):
    """Send message request payload."""

    from_entity: str
    to_address: str
    text: str
    session_id: str | None = None


@router.post("/send", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def send_message(
    request_data: SendMessageRequest,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Send text message from one local entity to target address."""
    sender_entity = resolve_sender_entity(current_host, request_data.from_entity)

    # 如果 to_address 不包含 ':'，说明是同 host 内的 entity_uid，补全为完整地址
    to_addr = request_data.to_address
    if ':' not in to_addr:
        to_addr = f"{current_host.uid}:{to_addr}"

    recipient_address = FPAddress(address=to_addr)
    session_id = SessionService(sender_entity).resolve_outbound_session_id(
        recipient_address,
        request_data.session_id,
    )

    text_message = Message(
        kind=MessageKind.INVOKE,
        payload=InvokePayload(text=request_data.text, session_id=session_id),
    )

    # 检查目标是否可达
    target_host_uid = recipient_address.host_uid
    delivery_status = "sent"
    warning_message = None

    # 检查路由可达性
    if target_host_uid != current_host.uid:
        # 检查是否是 child
        if target_host_uid in current_host.child_hosts:
            # 检查 child 是否连接
            if hasattr(current_host, 'child_clients') and target_host_uid not in current_host.child_clients:
                delivery_status = "offline"
                warning_message = "Target host is offline"
        else:
            # 需要转发给 parent
            if not current_host.parent_host:
                delivery_status = "unreachable"
                warning_message = "Cannot route to target host (no parent configured)"

    mail = await sender_entity.send_message(
        to=recipient_address,
        message=text_message,
    )

    # NOTE: 总是返回 SENT 状态，后续状态由 WebSocket 推送
    # mail.status 可能已经被 route_mail 异步更新，不应该返回给前端
    return StandardResponse[dict](
        success=True,
        message=warning_message or "Message sent successfully",
        data={
            "message_id": mail.message.message_id,
            "mail_id": mail.mail_id,  # Add mail_id for frontend tracking
            "from_entity_uid": sender_entity.uid,
            "to_address": request_data.to_address,
            "session_id": session_id,
            "delivery_status": delivery_status,
            "warning": warning_message,
            "status": "sent",  # Always return SENT, subsequent updates via WebSocket
        },
    )


def _format_message(mail_entry: dict) -> dict | None:
    """Format mail entry for frontend."""
    from loguru import logger

    try:
        mail_data = mail_entry.get("mail", {})
        metadata = mail_entry.get("metadata", {})

        mail = Mail.from_dict(mail_data)

        sender_address = mail.sender
        message_obj = mail.message

        if hasattr(message_obj, 'model_dump'):
            message_dict = message_obj.model_dump()
        elif isinstance(message_obj, dict):
            message_dict = message_obj
        else:
            logger.warning(f"Unexpected message type: {type(message_obj)}")
            return None

        sender_str = sender_address.address if hasattr(sender_address, 'address') else str(sender_address)
        recipient_list = []
        if hasattr(mail, 'recipient'):
            for r in mail.recipient:
                recipient_list.append(r.address if hasattr(r, 'address') else str(r))

        # 获取消息类型
        kind = message_dict.get("kind", "invoke")
        if hasattr(message_obj, 'kind'):
            kind = message_obj.kind.value if hasattr(message_obj.kind, 'value') else str(message_obj.kind)

        return {
            "message_id": message_dict.get("message_id", ""),
            "mail_id": mail_data.get("mail_id", ""),
            "kind": kind,
            "sender": sender_str,
            "recipient": recipient_list,
            "payload": message_dict.get("payload", {}),
            "timestamp": metadata.get("timestamp", ""),
            "direction": metadata.get("direction", ""),
            "is_read": metadata.get("is_read", False),
            "status": metadata.get("status", mail_data.get("status", "sent")),
        }

    except Exception as e:
        from loguru import logger
        logger.error(f"Failed to process mail entry: {e}")
        return None


@router.get("/{entity_uid}", response_model=StandardResponse[list[dict[str, Any]]])
@exception_wrapper(catch_http_exc=True)
async def get_messages(
    entity_uid: str,
    current_host: Annotated[Host, Depends(get_host_runtime)],
    limit: int = Query(default=100, ge=1, le=1000),
) -> StandardResponse[list[dict[str, Any]]]:
    """Get messages for an entity from its mailbox."""
    entity = current_host.get_entity(entity_uid)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_uid}")

    mailbox = Mailbox(entity_uid, Path(entity.mailbox_path))
    mails = mailbox.list_mails()
    mails = mails[-limit:] if len(mails) > limit else mails

    messages = []
    for mail_entry in mails:
        formatted = _format_message(mail_entry)
        if formatted:
            messages.append(formatted)

    return StandardResponse[list[dict[str, Any]]](
        success=True,
        message=f"Retrieved {len(messages)} messages",
        data=messages,
    )


class MarkReadRequest(BaseModel):
    """Mark messages as read request payload."""

    message_ids: list[str]


@router.post("/{entity_uid}/mark_read", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def mark_messages_read(
    entity_uid: str,
    request_data: MarkReadRequest,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Mark messages as read for an entity."""
    entity = current_host.get_entity(entity_uid)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_uid}")

    mailbox = Mailbox(entity_uid, Path(entity.mailbox_path))

    marked_count = 0
    for message_id in request_data.message_ids:
        if mailbox.mark_as_read(message_id):
            marked_count += 1

    return StandardResponse[dict](
        success=True,
        message=f"Marked {marked_count} messages as read",
        data={"marked_count": marked_count, "total_requested": len(request_data.message_ids)},
    )
