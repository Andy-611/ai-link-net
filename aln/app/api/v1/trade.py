"""Trade API — contract, payment, and market order operations."""

from __future__ import annotations

import asyncio
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from fp.trade import (
    ArbiterCheckPoint,
    ContractCreatePayload,
    aggregate_vendor_reputation,
    list_contract_reputation_contributions,
)
from fp import Entity, FPAddress, Host, Message, MessageKind, Session
from fp.core.session import SessionKind
from fp.core.checkpoint import build_approval_status_text
from fp.message import InvokePayload
from fp.trade.checkpoints import (
    OUTBOUND_CONTRACT_ACTION_KINDS,
    build_outbound_contract_action_request,
    request_outbound_contract_action_approval,
    request_outbound_contract_create_approval,
    request_outbound_pay_collect_approval,
    validate_outbound_contract_payload,
)
from fp.trade.payloads import PayCollectPayload

from aln.app.misc.common import resolve_sender_entity
from aln.app.misc.exception_handler import exception_wrapper
from aln.app.misc.provider import get_host_runtime, get_market_store
from aln.app.schemas import StandardResponse
from aln.app.schemas.market import (
    MarketOrder,
    MarketStore,
    OrderCategory,
    OrderStatus,
    OrderType,
    PublishOrderRequest,
    TradeMode,
)
from aln.app.service import HostClient

router = APIRouter(prefix="/trade", tags=["trade"])


class TradeSendRequest(BaseModel):
    """Send a trade message to the host's Arbiter."""

    from_entity: str = Field(..., description="Sender entity name or uid")
    kind: str = Field(..., description="MessageKind value (e.g. contract_create)")
    payload: dict[str, Any] = Field(default_factory=dict)
    to_entity: str | None = Field(
        default=None,
        description="Optional recipient (friend name/uid). If None, send to Arbiter.",
    )


class ContractWorkMessageRequest(BaseModel):
    """Send a real work message through a contract-linked session."""

    from_entity: str = Field(..., description="Sender entity name or uid")
    text: str = Field(..., min_length=1, description="Work message text")


def _get_arbiter_checkpoint(host: Host) -> tuple[Entity, ArbiterCheckPoint]:
    """Get arbiter entity and its checkpoint, or raise 404."""
    arbiter = host.get_arbiter()
    if arbiter is None:
        raise HTTPException(status_code=404, detail="No Arbiter registered on this host")
    cp = arbiter.get_checkpoint(ArbiterCheckPoint)
    if cp is None:
        raise HTTPException(status_code=500, detail="Arbiter has no ArbiterCheckPoint")
    return arbiter, cp


def _resolve_arbiter_client(host: Host) -> HostClient | None:
    """Return HostClient for Arbiter host, or None if local host IS the Arbiter."""
    if host.get_arbiter() is not None:
        return None
    parent_url = getattr(host, "parent_url", None)
    if not parent_url:
        return None
    return HostClient(base_url=parent_url, timeout=8.0)


def _has_session_participant(session: Session, participant: FPAddress) -> bool:
    return any(item.address == participant.address for item in session.participants)


def _ensure_contract_session(
    sender: Entity,
    *,
    session_id: str,
    session_name: str,
    recipient: FPAddress,
    contract_id: str,
) -> Session:
    session = sender.sessions.get(session_id)
    now = time.time()

    if session is None:
        session = Session(
            session_id=session_id,
            name=session_name,
            participants=[recipient],
            kind=SessionKind.CONTRACT_WORK,
            metadata={
                "contract_id": contract_id,
                "session_kind": "contract_work",
            },
            created_at=now,
            updated_at=now,
        )
        sender.sessions[session_id] = session
    else:
        if not _has_session_participant(session, recipient):
            session.participants.append(recipient)
        if not session.name:
            session.name = session_name
        if session.kind != SessionKind.CONTRACT_WORK:
            session.kind = SessionKind.CONTRACT_WORK
        session.metadata.setdefault("contract_id", contract_id)
        session.metadata.setdefault("session_kind", "contract_work")
        session.updated_at = now

    sender.save()
    return session


@router.post("/send", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def trade_send(
    request_data: TradeSendRequest,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Send a trade message (contract or payment) to the Arbiter."""
    sender = resolve_sender_entity(current_host, request_data.from_entity)

    try:
        kind = MessageKind(request_data.kind)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid message kind: {request_data.kind}")

    response_message = f"Trade message sent: {kind.value}"
    status_message: str | None = None

    if kind == MessageKind.CONTRACT_CREATE and request_data.to_entity is None:
        payload = ContractCreatePayload.model_validate(request_data.payload)
        approval_status = await request_outbound_contract_create_approval(sender, payload)
        if approval_status == "pending":
            status_message = build_approval_status_text("合同创建进入审批流程")
            response_message = status_message
        elif approval_status == "blocked":
            response_message = "Contract create blocked: no arbiter configured"
        await asyncio.sleep(0.15)
    elif kind in OUTBOUND_CONTRACT_ACTION_KINDS and request_data.to_entity is None:
        payload = validate_outbound_contract_payload(kind, request_data.payload)
        approval_status = await request_outbound_contract_action_approval(sender, kind, payload)
        if approval_status == "pending":
            status_message = build_approval_status_text(
                build_outbound_contract_action_request(kind, payload).process_text,
            )
            response_message = status_message
        elif approval_status == "blocked":
            response_message = f"Contract action blocked: {kind.value}"
        await asyncio.sleep(0.15)
    elif kind == MessageKind.PAY_COLLECT:
        pay_payload = PayCollectPayload.model_validate(request_data.payload)
        if request_data.to_entity is None:
            status_message = (
                "当前 Arbiter 不支持 ESCROW 模式收款，请使用 DIRECT 模式（默认）。\n"
                "CLI 示例：aln pay collect -e <entity> --payer <payer> --amount 100 --receipt <link>"
            )
            response_message = status_message
        else:
            approval_status = await request_outbound_pay_collect_approval(
                sender, pay_payload, to_entity=request_data.to_entity,
            )
            if approval_status == "pending":
                status_message = build_approval_status_text("收款流程进入审批流程")
                response_message = status_message
        await asyncio.sleep(0.15)
    else:
        msg = Message(kind=kind, payload=request_data.payload)
        if request_data.to_entity:
            await sender.send_message(to=request_data.to_entity, message=msg)
        else:
            if not sender.arbiter:
                raise HTTPException(status_code=404, detail="No Arbiter configured for this entity")
            await sender.send_message(to=sender.arbiter, message=msg)
        await asyncio.sleep(0.15)

    arbiter_data: dict[str, Any] = {}
    arbiter = current_host.get_arbiter()
    if arbiter:
        cp = arbiter.get_checkpoint(ArbiterCheckPoint)
        if cp:
            arbiter_data = {
                "contracts": {cid: c.model_dump(mode="json") for cid, c in cp.contracts.items()},
                "payments": {pid: p.model_dump(mode="json") for pid, p in cp.payments.items()},
            }

    return StandardResponse[dict](
        success=True,
        message=response_message,
        data={
            "kind": kind.value,
            "from_entity": sender.uid,
            "status_message": status_message,
            **arbiter_data,
        },
    )


@router.get("/contracts", response_model=StandardResponse[list[dict]])
@exception_wrapper(catch_http_exc=True)
async def list_contracts(
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[list[dict]]:
    """List all contracts managed by the Arbiter."""
    _, arbiter_cp = _get_arbiter_checkpoint(current_host)
    contracts = [c.model_dump(mode="json") for c in arbiter_cp.contracts.values()]
    return StandardResponse[list[dict]](
        success=True,
        message=f"{len(contracts)} contract(s)",
        data=contracts,
    )


@router.get("/contracts/{contract_id}", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def get_contract(
    contract_id: str,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Get contract details."""
    _, arbiter_cp = _get_arbiter_checkpoint(current_host)
    contract = arbiter_cp.contracts.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
    return StandardResponse[dict](
        success=True,
        message=f"Contract {contract_id}",
        data=contract.model_dump(mode="json"),
    )


@router.get("/reputation/vendors", response_model=StandardResponse[list[dict]])
@exception_wrapper(catch_http_exc=True)
async def list_vendor_reputation(
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[list[dict]]:
    """List derived vendor reputation profiles from signed contracts."""
    _, arbiter_cp = _get_arbiter_checkpoint(current_host)
    profiles = [
        profile.model_dump(mode="json")
        for profile in aggregate_vendor_reputation(arbiter_cp.contracts.values())
    ]
    return StandardResponse[list[dict]](
        success=True,
        message=f"{len(profiles)} vendor reputation profile(s)",
        data=profiles,
    )


@router.get("/reputation/contracts", response_model=StandardResponse[list[dict]])
@exception_wrapper(catch_http_exc=True)
async def list_contract_reputation(
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[list[dict]]:
    """List contract-level vendor reputation contribution rows."""
    _, arbiter_cp = _get_arbiter_checkpoint(current_host)
    rows = [
        row.model_dump(mode="json")
        for row in list_contract_reputation_contributions(arbiter_cp.contracts.values())
    ]
    return StandardResponse[list[dict]](
        success=True,
        message=f"{len(rows)} contract reputation row(s)",
        data=rows,
    )


@router.post("/contracts/{contract_id}/messages", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def send_contract_message(
    contract_id: str,
    request_data: ContractWorkMessageRequest,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Send a real work message through the contract's linked work session."""
    sender = resolve_sender_entity(current_host, request_data.from_entity)
    _, arbiter_cp = _get_arbiter_checkpoint(current_host)

    contract = arbiter_cp.contracts.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")

    if sender.uid not in {contract.party_a.entity_uid, contract.party_b.entity_uid}:
        raise HTTPException(status_code=403, detail="Only contract participants can send work messages")

    recipient = contract.party_b if sender.uid == contract.party_a.entity_uid else contract.party_a
    session_id = contract.work_session_id or f"contract:{contract.contract_id}"
    session_name = contract.work_session_name or contract.title

    _ensure_contract_session(
        sender,
        session_id=session_id,
        session_name=session_name,
        recipient=recipient,
        contract_id=contract.contract_id,
    )

    text_message = Message(
        kind=MessageKind.INVOKE,
        payload=InvokePayload(text=request_data.text, session_id=session_id),
    )
    mail = await sender.send_message(to=recipient, message=text_message)

    return StandardResponse[dict](
        success=True,
        message="Contract work message sent",
        data={
            "contract_id": contract.contract_id,
            "session_id": session_id,
            "session_name": session_name,
            "message_id": mail.message.message_id,
            "mail_id": mail.mail_id,
            "from_entity": sender.uid,
            "to_address": recipient.address,
        },
    )


@router.get("/payments", response_model=StandardResponse[list[dict]])
@exception_wrapper(catch_http_exc=True)
async def list_payments(
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[list[dict]]:
    """List all payments managed by the Arbiter."""
    _, arbiter_cp = _get_arbiter_checkpoint(current_host)
    payments = [p.model_dump(mode="json") for p in arbiter_cp.payments.values()]
    return StandardResponse[list[dict]](
        success=True,
        message=f"{len(payments)} payment(s)",
        data=payments,
    )


@router.get("/balance/{entity_spec}", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def get_balance(
    entity_spec: str,
    current_host: Annotated[Host, Depends(get_host_runtime)],
) -> StandardResponse[dict]:
    """Query entity balance on the Arbiter's ledger."""
    entity = resolve_sender_entity(current_host, entity_spec)
    _, arbiter_cp = _get_arbiter_checkpoint(current_host)
    balance = arbiter_cp.ledger.balance(entity.uid)
    available = arbiter_cp.ledger.available(entity.uid)
    frozen = balance - available
    return StandardResponse[dict](
        success=True,
        message=f"Balance for {entity.name}",
        data={
            "entity_uid": entity.uid,
            "entity_name": entity.name,
            "balance": balance,
            "available": available,
            "frozen": frozen,
        },
    )


# ==================== Market Orders (app-layer) ====================


@router.post("/orders", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def publish_order(
    request_data: PublishOrderRequest,
    current_host: Annotated[Host, Depends(get_host_runtime)],
    store: Annotated[MarketStore, Depends(get_market_store)],
) -> StandardResponse[dict]:
    """Publish a new market order (demand or supply)."""
    address = request_data.publisher_address
    if not address:
        entity = resolve_sender_entity(current_host, request_data.publisher)
        address = f"{current_host.uid}:{entity.uid}"

    arbiter_client = _resolve_arbiter_client(current_host)
    if arbiter_client is not None:
        payload = request_data.model_dump(mode="json")
        payload["publisher_address"] = address
        data = arbiter_client.market_publish(payload)
        return StandardResponse[dict](
            success=True,
            message=f"Order published: {data.get('order_id', '?')}",
            data=data,
        )

    if request_data.trade_mode == TradeMode.AUTONOMOUS:
        _get_arbiter_checkpoint(current_host)
    order = store.publish(request_data, publisher_address=address)
    return StandardResponse[dict](
        success=True,
        message=f"Order published: {order.order_id}",
        data=order.model_dump(mode="json"),
    )


@router.get("/orders", response_model=StandardResponse[list[dict]])
@exception_wrapper(catch_http_exc=True)
async def list_orders(
    current_host: Annotated[Host, Depends(get_host_runtime)],
    store: Annotated[MarketStore, Depends(get_market_store)],
    type: OrderType | None = Query(None, description="Filter by order type"),
    status: OrderStatus | None = Query(None, description="Filter by status"),
    publisher: str | None = Query(None, description="Filter by publisher uid"),
    category: OrderCategory | None = Query(None, description="Filter by category"),
    trade_mode: TradeMode | None = Query(None, description="Filter by trade mode"),
) -> StandardResponse[list[dict]]:
    """List market orders with optional filters."""
    arbiter_client = _resolve_arbiter_client(current_host)
    if arbiter_client is not None:
        data = arbiter_client.market_list(
            order_type=type.value if type else None,
            status=status.value if status else None,
            publisher=publisher,
            category=category.value if category else None,
            trade_mode=trade_mode.value if trade_mode else None,
        )
        return StandardResponse[list[dict]](
            success=True, message=f"{len(data)} order(s)", data=data,
        )

    orders = store.list_orders(
        order_type=type, status=status, publisher=publisher,
        category=category, trade_mode=trade_mode,
    )
    return StandardResponse[list[dict]](
        success=True,
        message=f"{len(orders)} order(s)",
        data=[o.model_dump(mode="json") for o in orders],
    )


@router.get("/orders/{order_id}", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def get_order(
    order_id: str,
    current_host: Annotated[Host, Depends(get_host_runtime)],
    store: Annotated[MarketStore, Depends(get_market_store)],
) -> StandardResponse[dict]:
    """Get a market order by ID."""
    arbiter_client = _resolve_arbiter_client(current_host)
    if arbiter_client is not None:
        data = arbiter_client.market_get(order_id)
        return StandardResponse[dict](success=True, message=f"Order {order_id}", data=data)

    order = store.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")
    return StandardResponse[dict](
        success=True,
        message=f"Order {order_id}",
        data=order.model_dump(mode="json"),
    )


@router.post("/orders/{order_id}/archive", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def archive_order(
    order_id: str,
    current_host: Annotated[Host, Depends(get_host_runtime)],
    store: Annotated[MarketStore, Depends(get_market_store)],
    requester: str = Query(..., description="Requester entity uid"),
) -> StandardResponse[dict]:
    """Archive a market order (publisher only)."""
    arbiter_client = _resolve_arbiter_client(current_host)
    if arbiter_client is not None:
        data = arbiter_client.market_archive(order_id, requester)
        return StandardResponse[dict](
            success=True, message=f"Order archived: {order_id}", data=data,
        )

    try:
        resolve_sender_entity(current_host, requester)
    except HTTPException:
        pass
    order = store.archive(order_id, requester_uid=requester)
    if order is None:
        raise HTTPException(status_code=403, detail="Order not found or not authorized")
    return StandardResponse[dict](
        success=True,
        message=f"Order archived: {order_id}",
        data=order.model_dump(mode="json"),
    )


@router.delete("/orders/{order_id}", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def delete_order(
    order_id: str,
    current_host: Annotated[Host, Depends(get_host_runtime)],
    store: Annotated[MarketStore, Depends(get_market_store)],
    requester: str = Query(..., description="Requester entity uid"),
) -> StandardResponse[dict]:
    """Delete a market order (publisher only)."""
    arbiter_client = _resolve_arbiter_client(current_host)
    if arbiter_client is not None:
        arbiter_client.market_delete(order_id, requester)
        return StandardResponse[dict](
            success=True, message=f"Order deleted: {order_id}",
            data={"order_id": order_id},
        )

    try:
        resolve_sender_entity(current_host, requester)
    except HTTPException:
        pass
    if not store.delete(order_id, requester_uid=requester):
        raise HTTPException(status_code=403, detail="Order not found or not authorized")
    return StandardResponse[dict](
        success=True,
        message=f"Order deleted: {order_id}",
        data={"order_id": order_id},
    )
