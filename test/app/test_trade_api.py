"""Smoke tests for trade API contract detail and work-session flows."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from aln.app.service.host_server import HostServer
from aln.app.api.v1.trade import (
    ContractWorkMessageRequest,
    TradeSendRequest,
    get_contract,
    list_contract_reputation,
    list_vendor_reputation,
    list_contracts,
    send_contract_message,
    trade_send,
)
from fp import Entity, EntityKind, Host, Message, MessageKind
from fp.mailbox import Mailbox
from fp.trade import (
    ArbiterCheckPoint,
    Contract,
    ContractActionPayload,
    ContractCreatePayload,
    ContractRatePayload,
    DeliveryArtifact,
    DeliveryEvidence,
    ExecutionCostReport,
    FundingMode,
)


async def _create_active_contract() -> tuple[Host, Entity, Entity, Contract]:
    """Create one active contract that already carries trust evidence."""
    host = Host(name="TrustHub")
    arbiter = host.register_entity(name="Arbiter", kind=EntityKind.ARBITER)
    arbiter_cp = arbiter.get_checkpoint(ArbiterCheckPoint)
    assert arbiter_cp is not None
    alice = host.register_entity(name="Alice", kind=EntityKind.HUMAN)
    bob = host.register_entity(name="Bob", kind=EntityKind.HUMAN)

    alice.add_friend(arbiter.entity_card)
    arbiter.add_friend(alice.entity_card)
    bob.add_friend(arbiter.entity_card)
    arbiter.add_friend(bob.entity_card)
    alice.add_friend(bob.entity_card)
    bob.add_friend(alice.entity_card)

    await alice.send_message(
        to=arbiter.entity_card,
        message=Message(
            kind=MessageKind.CONTRACT_CREATE,
            payload=ContractCreatePayload(
                party_a=alice.address,
                party_b=bob.address,
                party_a_card=alice.entity_card,
                party_b_card=bob.entity_card,
                title="Trade API smoke",
                description="contract detail + work session smoke",
                amount=120,
                funding_mode=FundingMode.DIRECT,
            ).model_dump(),
        ),
    )
    await asyncio.sleep(0.05)

    contract = next(iter(arbiter_cp.contracts.values()))

    await bob.send_message(
        to=arbiter.entity_card,
        message=Message(
            kind=MessageKind.CONTRACT_APPROVE,
            payload=ContractActionPayload(
                contract_id=contract.contract_id,
                expected_status=contract.status,
                revision=contract.draft_version,
                terms_hash=contract.terms_hash,
                source_snapshot_hash=contract.current_snapshot_hash,
            ).model_dump(),
        ),
    )
    await asyncio.sleep(0.05)

    return host, alice, bob, arbiter_cp.contracts[contract.contract_id]


async def _create_rated_contract() -> tuple[Host, Entity, Entity, Contract]:
    host, alice, bob, contract = await _create_active_contract()
    arbiter = host.get_arbiter()
    assert arbiter is not None
    arbiter_cp = arbiter.get_checkpoint(ArbiterCheckPoint)
    assert arbiter_cp is not None

    await bob.send_message(
        to=arbiter.entity_card,
        message=Message(
            kind=MessageKind.CONTRACT_COMPLETE,
            payload=ContractActionPayload(
                contract_id=contract.contract_id,
                expected_status=contract.status,
                revision=contract.draft_version,
                terms_hash=contract.terms_hash,
                source_snapshot_hash=contract.current_snapshot_hash,
                reason="Structured delivery for API reputation test",
                delivery=DeliveryEvidence(
                    delivery_id="delivery-v1",
                    version="v1.0.0",
                    summary="Vendor portal delivery",
                    artifacts=[
                        DeliveryArtifact(
                            kind="preview",
                            uri="https://preview.example/v1",
                            label="Preview",
                        ),
                    ],
                    source_session_id=contract.work_session_id,
                    produced_by=bob.address,
                    produced_at=time.time(),
                ),
                execution_costs=[
                    ExecutionCostReport(
                        actor=bob.address,
                        phase="implementation",
                        provider="codex",
                        model="gpt-5-codex",
                        input_tokens=800,
                        output_tokens=300,
                        cost_usd=0.19,
                        runtime_ms=110000,
                        recorded_at=time.time(),
                    ),
                ],
            ).model_dump(),
        ),
    )
    await asyncio.sleep(0.05)

    contract = arbiter_cp.contracts[contract.contract_id]
    await alice.send_message(
        to=arbiter.entity_card,
        message=Message(
            kind=MessageKind.CONTRACT_ACCEPT,
            payload=ContractActionPayload(
                contract_id=contract.contract_id,
                expected_status=contract.status,
                revision=contract.draft_version,
                terms_hash=contract.terms_hash,
                source_snapshot_hash=contract.current_snapshot_hash,
                reason="Accepted",
            ).model_dump(),
        ),
    )
    await asyncio.sleep(0.05)

    contract = arbiter_cp.contracts[contract.contract_id]
    await alice.send_message(
        to=arbiter.entity_card,
        message=Message(
            kind=MessageKind.CONTRACT_RATE,
            payload=ContractRatePayload(
                contract_id=contract.contract_id,
                rating=5,
                review="Great vendor delivery",
                expected_status=contract.status,
                revision=contract.draft_version,
                terms_hash=contract.terms_hash,
                source_snapshot_hash=contract.current_snapshot_hash,
            ).model_dump(),
        ),
    )
    await asyncio.sleep(0.05)

    return host, alice, bob, arbiter_cp.contracts[contract.contract_id]


def test_trade_contract_detail_api_exposes_trust_evidence() -> None:
    """Contract detail API should expose the evidence needed by the UI."""
    async def run() -> dict:
        host, _, _, contract = await _create_active_contract()
        list_response = await list_contracts(current_host=host)
        assert list_response.data is not None
        assert len(list_response.data) == 1

        detail_response = await get_contract(contract.contract_id, current_host=host)
        assert detail_response.data is not None
        return detail_response.data

    detail = asyncio.run(run())

    assert detail["contract_id"]
    assert detail["work_session_id"] == f"contract:{detail['contract_id']}"
    assert detail["work_session_name"] == detail["title"]
    assert len(detail["snapshot_history"]) == 2
    assert len(detail["approvals"]) == 2
    assert {item["party_role"] for item in detail["approvals"]} == {"party_a", "party_b"}
    assert detail["attestation"]["snapshot_hash"] == detail["current_snapshot_hash"]
    assert detail["attestation"]["prev_snapshot_hash"] == detail["prev_snapshot_hash"]


def test_trade_contract_work_message_api_binds_to_contract_session() -> None:
    """Contract work message API should reuse the contract-scoped session."""
    async def run() -> tuple[Entity, Entity, Contract, dict]:
        host, alice, bob, contract = await _create_active_contract()
        response = await send_contract_message(
            contract.contract_id,
            ContractWorkMessageRequest(
                from_entity=bob.uid,
                text="Kickoff update from Bob",
            ),
            current_host=host,
        )
        assert response.data is not None
        return alice, bob, contract, response.data

    alice, bob, contract, payload = asyncio.run(run())
    assert payload["contract_id"] == contract.contract_id
    assert payload["session_id"] == contract.work_session_id
    assert payload["session_name"] == contract.work_session_name
    assert bob.sessions[contract.work_session_id].metadata["contract_id"] == contract.contract_id

    inbox = Mailbox(alice.uid, Path(alice.mailbox_path)).list_mails(direction="inbound")
    session_messages = [
        entry
        for entry in inbox
        if entry["mail"]["message"]["payload"].get("session_id") == contract.work_session_id
    ]

    assert len(session_messages) == 1
    assert session_messages[0]["mail"]["message"]["payload"]["text"] == "Kickoff update from Bob"


def test_trade_send_contract_accept_returns_pending_status_message() -> None:
    """Sender-side contract action approval should return immediately with status text."""

    async def run() -> tuple[str, dict]:
        host = Host(name="TradeApprovalHost")
        arbiter = host.register_entity(name="Arbiter", kind=EntityKind.ARBITER)
        owner = host.register_entity(name="Owner", kind=EntityKind.HUMAN)
        client = host.register_entity(name="Client", kind=EntityKind.HUMAN)
        client.owner = owner.address
        client.arbiter = arbiter.address

        response = await trade_send(
            TradeSendRequest(
                from_entity=client.uid,
                kind=MessageKind.CONTRACT_ACCEPT.value,
                payload={"contract_id": "ctr_api_pending", "reason": "ship it"},
            ),
            current_host=host,
        )
        assert response.data is not None
        return response.message, response.data

    message, data = asyncio.run(run())
    assert "合同验收进入审批流程" in message
    assert "合同验收进入审批流程" in (data.get("status_message") or "")


def test_trade_send_contract_amend_returns_pending_status_message() -> None:
    """Sender-side contract amend approval should return immediately with status text."""

    async def run() -> tuple[str, dict]:
        host = Host(name="TradeAmendHost")
        arbiter = host.register_entity(name="Arbiter", kind=EntityKind.ARBITER)
        owner = host.register_entity(name="Owner", kind=EntityKind.HUMAN)
        creator = host.register_entity(name="Creator", kind=EntityKind.HUMAN)
        creator.owner = owner.address
        creator.arbiter = arbiter.address

        response = await trade_send(
            TradeSendRequest(
                from_entity=creator.uid,
                kind=MessageKind.CONTRACT_AMEND.value,
                payload={"contract_id": "ctr_api_amend", "title": "v2"},
            ),
            current_host=host,
        )
        assert response.data is not None
        return response.message, response.data

    message, data = asyncio.run(run())
    assert "合同修改进入审批流程" in message
    assert "合同修改进入审批流程" in (data.get("status_message") or "")


def test_arbiter_notifies_parties_without_friend_cards() -> None:
    """HostServer should auto-friend entities with Arbiter before trade notifications."""

    async def run() -> list[dict]:
        host = HostServer(name="NoFriendArbiterHost", bind_host="127.0.0.1", port=7001)
        arbiter = host.register_entity(name="Arbiter", kind=EntityKind.ARBITER)
        alice = host.register_entity(name="Alice", kind=EntityKind.HUMAN)
        bob = host.register_entity(name="Bob", kind=EntityKind.HUMAN)

        assert arbiter.uid in alice.friends
        assert arbiter.uid in bob.friends

        await alice.send_message(
            to=arbiter.address,
            message=Message(
                kind=MessageKind.CONTRACT_CREATE,
                payload=ContractCreatePayload(
                    party_a=alice.address,
                    party_b=bob.address,
                    party_a_card=alice.entity_card,
                    party_b_card=bob.entity_card,
                    title="No friend fallback",
                    description="arbiter should still notify Bob",
                    amount=88,
                    funding_mode=FundingMode.DIRECT,
                ).model_dump(),
            ),
        )
        await asyncio.sleep(0.05)
        return Mailbox(bob.uid, Path(bob.mailbox_path)).list_mails(direction="inbound")

    inbox = asyncio.run(run())
    assert any(
        entry["mail"]["message"]["kind"] == MessageKind.CONTRACT_STATUS.value
        for entry in inbox
    )


def test_trade_vendor_reputation_api_exposes_derived_profiles() -> None:
    """Vendor reputation API should expose derived profiles from signed contracts."""

    async def run() -> list[dict]:
        host, _, _, _ = await _create_rated_contract()
        response = await list_vendor_reputation(current_host=host)
        assert response.data is not None
        return response.data

    profiles = asyncio.run(run())
    assert len(profiles) == 1

    profile = profiles[0]
    assert profile["role"] == "party_b"
    assert profile["overall_score"] >= 80
    assert profile["confidence"] > 0
    assert profile["sample_size"] == 1
    assert profile["quality_score"] >= 95
    assert profile["recent_events"][0]["outcome"] == "accepted"


def test_trade_contract_reputation_api_explains_scored_and_pending_contracts() -> None:
    """Contract reputation API should explain why contracts are or are not yet scored."""

    async def run() -> tuple[list[dict], list[dict]]:
        active_host, _, _, _ = await _create_active_contract()
        active_rows = (await list_contract_reputation(current_host=active_host)).data
        assert active_rows is not None

        rated_host, _, _, rated_contract = await _create_rated_contract()
        rated_rows = (await list_contract_reputation(current_host=rated_host)).data
        assert rated_rows is not None
        return active_rows, [row for row in rated_rows if row["contract_id"] == rated_contract.contract_id]

    active_rows, rated_rows = asyncio.run(run())

    assert len(active_rows) == 1
    assert active_rows[0]["contributes"] is False
    assert "not scored yet" in active_rows[0]["reason"].lower() or "in progress" in active_rows[0]["reason"].lower()

    assert len(rated_rows) == 1
    assert rated_rows[0]["contributes"] is True
    assert rated_rows[0]["contract_score"] >= 80
    assert rated_rows[0]["feature"]["reliability_score"] == 1.0
