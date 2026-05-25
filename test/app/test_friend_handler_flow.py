from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from aln.app.handlers.agent_handler import AgentHandler
from fp.core.base import EntityKind
from fp.core.checkpoint import HandlerBridgeCheckPoint
from fp.host import Host
from fp.mail import Mail
from fp.message import FriendAcceptPayload, FriendRejectPayload, Message, MessageKind


@pytest.mark.parametrize(
    ("message_kind", "payload_type", "should_add_friend"),
    [
        (MessageKind.FRIEND_ACCEPT, FriendAcceptPayload, True),
        (MessageKind.FRIEND_REJECT, FriendRejectPayload, False),
    ],
)
@pytest.mark.asyncio
async def test_friend_response_reaches_agent_handler(
    tmp_path,
    message_kind,
    payload_type,
    should_add_friend,
):
    """Friend accept/reject should continue through the handler bridge."""

    def _drop_task(coro):
        coro.close()
        return MagicMock()

    host = Host(name="TestHost", data_dir=str(tmp_path))
    receiver = host.register_entity(name="Receiver", kind=EntityKind.AGENT)
    sender = host.register_entity(name="Sender", kind=EntityKind.AGENT)

    handler = AgentHandler.__new__(AgentHandler)
    handler.entity = receiver
    handler.adapter = MagicMock()
    handler._queue = asyncio.Queue()
    handler._loop_task = None
    handler._running_summary = "idle"
    handler.provider = "mock"
    handler.config = MagicMock()

    receiver.add_checkpoint(
        HandlerBridgeCheckPoint(
            name="handler_bridge",
            order=900,
            message_kinds=set(MessageKind),
            handler=handler,
        )
    )

    message = Message(
        kind=message_kind,
        payload=payload_type(
            sender_card=sender.entity_card,
            text=f"{sender.name} {'accepted' if should_add_friend else 'rejected'} your friend request",
        ),
    )

    with patch("aln.app.handlers.agent_handler.asyncio.create_task", side_effect=_drop_task):
        sealed_mail = Mail.seal(
            sender=sender.address,
            recipient=receiver.address,
            message=message,
            sign_private_key=sender.sign_private_key,
            encrypt_public_key=None,
        )
        await receiver.receive_mail(sealed_mail)

    assert handler._queue.qsize() == 1
    queued_message = handler._queue.get_nowait().message
    assert queued_message.kind == message_kind
    assert (sender.uid in receiver.friends) is should_add_friend
