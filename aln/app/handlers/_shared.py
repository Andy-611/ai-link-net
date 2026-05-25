"""Shared helpers for application-layer handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fp.core.wellknown import FPAddress
from fp.message import InvokePayload, Message, MessageKind

if TYPE_CHECKING:
    from fp.entity import Entity


def extract_session_id(payload: Any) -> str | None:
    """Pull session_id from an InvokePayload or legacy dict payload."""
    if isinstance(payload, InvokePayload):
        return payload.session_id
    if isinstance(payload, dict):
        value = payload.get("session_id")
        if isinstance(value, str):
            return value
    return None


async def reply_invoke(
    entity: Entity,
    original: Message,
    *,
    text: str,
    session_id: str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Send an INVOKE reply back to the original sender.

    Returns silently if the original message has no sender_address in metadata.
    """
    sender_address = original.metadata.get("sender_address")
    if not sender_address:
        return
    payload: dict[str, Any] = {"text": text, "session_id": session_id}
    if extra:
        payload.update(extra)
    response = Message(kind=MessageKind.INVOKE, payload=payload)
    await entity.send_message(FPAddress(address=sender_address), response)
