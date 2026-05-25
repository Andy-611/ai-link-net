"""Session API regression tests."""

from __future__ import annotations

import asyncio

from aln.app.api.v1.messages import SendMessageRequest, send_message
from aln.app.api.v1.sessions import (
    CreateSessionRequest,
    create_session,
    delete_session,
    list_sessions,
)
from aln.app.api.v1.trade import _ensure_contract_session
from aln.app.service import SessionService
from fp import Entity, EntityKind, Host, Session
from fp.core.session import SessionKind


def _create_chat_pair() -> tuple[Host, Entity, Entity]:
    """Create two local friends for chat/session tests."""
    host = Host(name="SessionHub")
    alice = host.register_entity(name="Alice", kind=EntityKind.HUMAN)
    bob = host.register_entity(name="Bob", kind=EntityKind.AGENT)
    alice.add_friend(bob.entity_card)
    bob.add_friend(alice.entity_card)
    alice.save()
    bob.save()
    return host, alice, bob


def test_send_message_without_explicit_session_uses_hidden_implicit_session() -> None:
    """Unscoped chat send should never reuse the latest visible session."""

    async def run() -> tuple[Entity, str]:
        host, alice, bob = _create_chat_pair()
        session = await create_session(
            alice.uid,
            CreateSessionRequest(contact_uid=bob.uid, name="Focused task"),
            target_entity=alice,
        )
        assert session.data is not None

        response = await send_message(
            SendMessageRequest(
                from_entity=alice.uid,
                to_address=bob.address.address,
                text="hello from all messages",
                session_id=None,
            ),
            current_host=host,
        )
        assert response.data is not None
        return alice, response.data["session_id"]

    alice, session_id = asyncio.run(run())
    service = SessionService(alice)
    implicit_session_id = service.build_implicit_session_id(
        alice.address,
        next(iter(alice.friends.values())).address,
    )

    assert session_id == implicit_session_id
    assert session_id in alice.sessions
    assert alice.sessions[session_id].kind == SessionKind.IMPLICIT
    assert all(
        session.session_id == implicit_session_id or session.kind == SessionKind.MANUAL
        for session in alice.sessions.values()
    )


def test_list_sessions_only_returns_manual_chat_sessions() -> None:
    """Session history should hide implicit and workflow sessions."""

    async def run() -> tuple[str, list[str]]:
        _, alice, bob = _create_chat_pair()
        service = SessionService(alice)
        manual = service.create_manual_session(bob.uid, "Visible session")

        implicit_session_id = service.build_implicit_session_id(alice.address, bob.address)
        alice.sessions[implicit_session_id] = Session(
            session_id=implicit_session_id,
            participants=[bob.address],
        )
        _ensure_contract_session(
            alice,
            session_id="contract:test-contract",
            session_name="Contract flow",
            recipient=bob.address,
            contract_id="test-contract",
        )
        alice.save()

        response = await list_sessions(
            alice.uid,
            target_entity=alice,
            contact_uid=bob.uid,
        )
        assert response.data is not None
        return manual.session_id, [item.session_id for item in response.data]

    manual_session_id, session_ids = asyncio.run(run())
    assert session_ids == [manual_session_id]


def test_delete_last_manual_session_clears_persisted_sessions() -> None:
    """Deleting the final session should not resurrect stale data after reload."""

    async def run() -> tuple[str, Host]:
        _, alice, bob = _create_chat_pair()
        response = await create_session(
            alice.uid,
            CreateSessionRequest(contact_uid=bob.uid, name="Disposable"),
            target_entity=alice,
        )
        assert response.data is not None
        session_id = response.data.session_id
        await delete_session(alice.uid, session_id, target_entity=alice)
        return alice.uid, alice.host

    entity_uid, host = asyncio.run(run())
    reloaded = Entity.load(entity_uid, host)
    assert reloaded.sessions == {}
