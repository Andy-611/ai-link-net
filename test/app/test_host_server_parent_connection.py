"""Tests for parent connection behavior in HostServer."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from aln.app.service.host_server import HostServer
from fp.core.base import EntityKind
from fp.host import Host
from fp.core.wellknown import FPAddress
from fp.core.checkpoint import FriendRequestCheckPoint
from fp.trade.checkpoints import (
    ContractApprovalCheckPoint,
    PayClaimCheckPoint,
    PayCollectInboundCheckPoint,
    PayConfirmReceiptCheckPoint,
)


class _FakeWebSocket:
    """Minimal WebSocket stub for connect_to_parent tests."""

    def __init__(self) -> None:
        self.send = AsyncMock()


def _drop_task(coro):
    """Close coroutine to avoid background task warnings in unit tests."""
    coro.close()
    return MagicMock()


def test_connect_to_parent_disables_proxy() -> None:
    """HostServer should disable proxy when connecting parent websocket."""
    host_runtime = HostServer(
        name="dev",
        bind_host="0.0.0.0",
        port=7002,
    )
    host_runtime.parent_host = Host(
        name="hub",
        address=FPAddress(address="419e5703:0"),
        bind_host="127.0.0.1",
        port=7001,
    )

    fake_ws = _FakeWebSocket()

    with patch(
        "aln.app.service.host_server.websockets.connect",
        new=AsyncMock(return_value=fake_ws),
    ) as mock_connect, patch(
        "aln.app.service.host_server.asyncio.create_task",
        side_effect=_drop_task,
    ):
        asyncio.run(host_runtime.connect_to_parent("http://127.0.0.1:7001"))

    mock_connect.assert_awaited_once_with("ws://127.0.0.1:7001/ws", proxy=None)
    assert host_runtime.parent_ws is fake_ws
    fake_ws.send.assert_awaited_once()


def test_registering_owner_and_arbiter_backfills_existing_agents() -> None:
    """Late owner/arbiter registration should refresh existing agent relationships and policies."""
    host_runtime = HostServer(name="dev", bind_host="0.0.0.0", port=7002)

    agent = host_runtime.register_entity(name="worker", kind=EntityKind.AGENT)
    owner = host_runtime.register_entity(name="owner", kind=EntityKind.HUMAN)
    arbiter = host_runtime.register_entity(name="arbiter", kind=EntityKind.ARBITER)

    assert agent.owner == owner.address
    assert agent.arbiter == arbiter.address
    assert owner.uid in agent.friends
    assert agent.uid in owner.friends
    assert arbiter.uid in agent.friends
    assert agent.uid in arbiter.friends

    for checkpoint_type in (
        FriendRequestCheckPoint,
        ContractApprovalCheckPoint,
        PayCollectInboundCheckPoint,
        PayClaimCheckPoint,
        PayConfirmReceiptCheckPoint,
    ):
        checkpoint = agent.get_checkpoint(checkpoint_type)
        assert checkpoint is not None
        assert checkpoint.call_owner_policy == "always_call"
