"""Session management API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from fp import Entity, Session
from aln.app.schemas import StandardResponse
from aln.app.misc.exception_handler import exception_wrapper
from aln.app.misc.provider import get_target_entity
from aln.app.service import SessionService

router = APIRouter(prefix="/entities/{entity_uid}/sessions", tags=["sessions"])


class SessionInfo(BaseModel):
    """Session information for API response."""
    session_id: str
    name: str | None
    participants: list[str]
    created_at: float
    updated_at: float
    message_count: int = 0


class RenameSessionRequest(BaseModel):
    """Request to rename a session."""
    name: str = Field(..., min_length=1, max_length=100, description="New session name")


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    contact_uid: str = Field(..., description="Contact entity UID")
    name: str | None = Field(None, max_length=100, description="Session name")


def _to_session_info(session: Session) -> SessionInfo:
    """Convert a domain session to API response schema."""
    return SessionInfo(
        session_id=session.session_id,
        name=session.name,
        participants=[participant.address for participant in session.participants],
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
    )


@router.get("", response_model=StandardResponse[list[SessionInfo]])
@exception_wrapper(catch_http_exc=True)
async def list_sessions(
    entity_uid: str,
    target_entity: Annotated[Entity, Depends(get_target_entity)],
    contact_uid: str | None = None,
) -> StandardResponse[list[SessionInfo]]:
    """List all sessions for an entity, optionally filtered by contact."""
    service = SessionService(target_entity)
    sessions_list = [
        _to_session_info(session)
        for session in service.list_manual_sessions(contact_uid)
    ]

    return StandardResponse[list[SessionInfo]](
        success=True,
        message=f"Sessions list retrieved for entity: {entity_uid}",
        data=sessions_list,
    )


@router.post("", response_model=StandardResponse[SessionInfo])
@exception_wrapper(catch_http_exc=True)
async def create_session(
    entity_uid: str,
    request_data: CreateSessionRequest,
    target_entity: Annotated[Entity, Depends(get_target_entity)],
) -> StandardResponse[SessionInfo]:
    """Create a new session with a contact."""
    service = SessionService(target_entity)
    session = service.create_manual_session(
        contact_uid=request_data.contact_uid,
        name=request_data.name,
    )

    return StandardResponse[SessionInfo](
        success=True,
        message="Session created successfully",
        data=_to_session_info(session),
    )


@router.post("/{session_id}/rename", response_model=StandardResponse[SessionInfo])
@exception_wrapper(catch_http_exc=True)
async def rename_session(
    entity_uid: str,
    session_id: str,
    request_data: RenameSessionRequest,
    target_entity: Annotated[Entity, Depends(get_target_entity)],
) -> StandardResponse[SessionInfo]:
    """Rename a session."""
    service = SessionService(target_entity)
    session = service.rename_manual_session(session_id, request_data.name)

    return StandardResponse[SessionInfo](
        success=True,
        message="Session renamed successfully",
        data=_to_session_info(session),
    )


@router.delete("/{session_id}", response_model=StandardResponse[dict])
@exception_wrapper(catch_http_exc=True)
async def delete_session(
    entity_uid: str,
    session_id: str,
    target_entity: Annotated[Entity, Depends(get_target_entity)],
) -> StandardResponse[dict]:
    """Delete a session."""
    SessionService(target_entity).delete_manual_session(session_id)

    return StandardResponse[dict](
        success=True,
        message="Session deleted successfully",
        data={},
    )
