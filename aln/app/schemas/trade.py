"""Trade-related schemas for app APIs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from fp.trade import Contract, Payment


ContractActionType = Literal[
    "approve",
    "complete",
    "cancel",
    "accept",
    "rework",
    "rate",
]


class TradeSendRequest(BaseModel):
    """Send a trade message to the host Arbiter."""

    from_entity: str = Field(..., description="Sender entity name or uid")
    kind: str = Field(..., description="MessageKind value")
    payload: dict[str, object] = Field(default_factory=dict)


class TradeSendResponse(BaseModel):
    """Trade send result snapshot."""

    kind: str
    from_entity: str
    contracts: dict[str, Contract]
    payments: dict[str, Payment]


class ContractActionRequest(BaseModel):
    """Apply one typed contract action."""

    from_entity: str = Field(..., description="Actor entity name or uid")
    action: ContractActionType
    reason: str | None = None
    rating: int | None = None
    review: str | None = None
    expected_status: str | None = None
    revision: int | None = None
    terms_hash: str | None = None
    source_snapshot_hash: str | None = None


class ContractWorkMessageRequest(BaseModel):
    """Send a real work message through a contract-linked session."""

    from_entity: str = Field(..., description="Sender entity name or uid")
    text: str = Field(..., min_length=1, description="Work message text")


class ContractWorkMessageResponse(BaseModel):
    """Contract-linked work message result."""

    contract_id: str
    session_id: str
    session_name: str
    message_id: str
    mail_id: str
    from_entity: str
    to_address: str
