"""Session lifecycle and classification helpers."""

from __future__ import annotations

import hashlib
import time

from fastapi import HTTPException

from fp import Entity, FPAddress, Session
from fp.core.session import SessionKind


class SessionService:
    """Encapsulate chat session rules for one entity."""

    def __init__(self, entity: Entity):
        """Bind the service to one entity."""
        self.entity = entity

    @staticmethod
    def build_implicit_session_id(sender: FPAddress, recipient: FPAddress) -> str:
        """Build the stable implicit session id for one sender-recipient pair."""
        participants = sorted([sender.address, recipient.address])
        raw = "|".join(participants)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def session_matches_contact(session: Session, contact_uid: str) -> bool:
        """Check whether the session belongs to the given contact."""
        return any(participant.entity_uid == contact_uid for participant in session.participants)

    def list_manual_sessions(self, contact_uid: str | None = None) -> list[Session]:
        """Return visible chat sessions, newest first."""
        sessions = [
            session
            for session in self.entity.sessions.values()
            if session.kind == SessionKind.MANUAL
        ]
        if contact_uid:
            sessions = [
                session
                for session in sessions
                if self.session_matches_contact(session, contact_uid)
            ]
        return sorted(sessions, key=lambda session: session.updated_at, reverse=True)

    def create_manual_session(self, contact_uid: str, name: str | None = None) -> Session:
        """Create and persist one user-visible session."""
        contact_card = self.entity.friends.get(contact_uid)
        if contact_card is None:
            raise HTTPException(status_code=404, detail=f"Contact not found: {contact_uid}")

        now = time.time()
        session = Session(
            session_id=f"{contact_uid}-{int(now * 1000)}",
            name=name or f"Chat with {contact_card.name}",
            participants=[contact_card.address],
            kind=SessionKind.MANUAL,
            created_at=now,
            updated_at=now,
        )
        self.entity.sessions[session.session_id] = session
        self.entity.save()
        return session

    def rename_manual_session(self, session_id: str, name: str) -> Session:
        """Rename and persist one visible session."""
        session = self._get_manual_session(session_id)
        session.name = name
        session.updated_at = time.time()
        self.entity.save()
        return session

    def delete_manual_session(self, session_id: str) -> None:
        """Delete and persist one visible session."""
        self._get_manual_session(session_id)
        del self.entity.sessions[session_id]
        self.entity.save()

    def resolve_outbound_session_id(
        self,
        recipient: FPAddress,
        requested_session_id: str | None,
    ) -> str:
        """Resolve which session id should be attached to one outbound message."""
        if requested_session_id:
            return self._touch_existing_session(requested_session_id, recipient)
        return self._touch_implicit_session(recipient)

    def _get_manual_session(self, session_id: str) -> Session:
        """Load one visible session or raise a user-facing error."""
        session = self.entity.sessions.get(session_id)
        if session is None or session.kind != SessionKind.MANUAL:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return session

    def _touch_existing_session(self, session_id: str, recipient: FPAddress) -> str:
        """Refresh one explicit session before use."""
        session = self.entity.sessions.get(session_id)
        if session is None:
            implicit_session_id = self.build_implicit_session_id(self.entity.address, recipient)
            if session_id == implicit_session_id:
                return self._touch_implicit_session(recipient)
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        self._touch_session(session, recipient)
        self.entity.save()
        return session.session_id

    def _touch_implicit_session(self, recipient: FPAddress) -> str:
        """Refresh the hidden per-contact session used for continuous context."""
        session_id = self.build_implicit_session_id(self.entity.address, recipient)
        session = self.entity.sessions.get(session_id)
        if session is None:
            now = time.time()
            session = Session(
                session_id=session_id,
                participants=[recipient],
                kind=SessionKind.IMPLICIT,
                created_at=now,
                updated_at=now,
            )
            self.entity.sessions[session_id] = session
        else:
            self._touch_session(session, recipient)
        self.entity.save()
        return session_id

    @staticmethod
    def _touch_session(session: Session, recipient: FPAddress) -> None:
        """Update session membership and activity timestamp."""
        if not SessionService.session_matches_contact(session, recipient.entity_uid):
            session.participants.append(recipient)
        session.updated_at = time.time()
