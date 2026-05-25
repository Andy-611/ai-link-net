"""Handler for A2A v1.0 outbound — forwards INVOKE to external A2A agents."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from loguru import logger

from aln.app.adapters.a2a_client import (
    A2AAgentConfig,
    A2AClient,
    A2AMessageResult,
    create_a2a_client,
)
from aln.app.handlers._shared import extract_session_id, reply_invoke
from fp.core.session import Session, SessionKind
from fp.handler import BaseHandler
from fp.message import Message, MessageKind
from fp.utils.storage import get_storage_manager

if TYPE_CHECKING:
    from fp.entity import Entity

_CONTEXT_ID_KEY = "a2a.context_id"
_TASK_ID_KEY = "a2a.task_id"


class A2AHandler(BaseHandler):
    """Reads A2AAgentConfig from entity.metadata['a2a_config'],
    lazily creates an A2AClient, forwards INVOKE as A2A SendMessage,
    and maps FP session_id <-> A2A contextId via Session.external_refs.
    """

    def __init__(self, entity: Entity) -> None:
        super().__init__(entity)
        self._client: A2AClient | None = None

    async def _ensure_client_ready(self) -> A2AClient:
        if self._client is not None:
            return self._client

        raw = self.entity.metadata.get("a2a_config")
        if not raw:
            raise ValueError(
                f"Entity {self.entity.uid} missing 'a2a_config' in metadata"
            )

        config = A2AAgentConfig.model_validate(raw)
        self._client = create_a2a_client(config)

        try:
            card = await self._client.fetch_agent_card()
            self.entity.metadata["a2a_skills"] = [
                skill.model_dump() for skill in card.skills
            ]
            self.entity.metadata["a2a_capabilities"] = card.capabilities
            logger.info(
                f"[A2AHandler] {self.entity.name}: loaded AgentCard "
                f"({len(card.skills)} skills, version={card.version})"
            )
        except Exception as e:
            logger.warning(f"[A2AHandler] Failed to fetch AgentCard: {e}")

        return self._client

    async def handle(self, message: Message) -> None:
        if message.kind != MessageKind.INVOKE:
            logger.warning(f"[A2AHandler] Ignoring non-INVOKE message: {message.kind}")
            return

        text = self._extract_text(message.payload)
        session_id = extract_session_id(message.payload)
        if not text:
            logger.warning("[A2AHandler] INVOKE payload missing 'text'")
            return

        try:
            client = await self._ensure_client_ready()
        except Exception as e:
            logger.error(f"[A2AHandler] Client init failed: {e}")
            return

        session = self._ensure_session(session_id, message)
        context_id = session.external_refs.get(_CONTEXT_ID_KEY)

        try:
            result = await client.send_message(text, context_id=context_id)
        except Exception as e:
            logger.error(f"[A2AHandler] SendMessage failed: {e}")
            return

        self._persist_refs(session, result)
        extra: dict[str, Any] | None = None
        if result.is_error:
            extra = {"a2a_error": True, "a2a_state": result.state}
        await reply_invoke(
            self.entity, message,
            text=result.text,
            session_id=session.session_id,
            extra=extra,
        )

    @staticmethod
    def _extract_text(payload: Any) -> str:
        if hasattr(payload, "text"):
            return payload.text or ""
        if isinstance(payload, dict):
            value = payload.get("text")
            return value if isinstance(value, str) else ""
        return ""

    def _ensure_session(self, session_id: str | None, message: Message) -> Session:
        effective_id = session_id or self._auto_session_id(message)
        session = self.entity.sessions.get(effective_id)
        if session is not None:
            session.updated_at = time.time()
            return session
        session = Session(session_id=effective_id, kind=SessionKind.IMPLICIT)
        self.entity.sessions[effective_id] = session
        return session

    def _auto_session_id(self, message: Message) -> str:
        sender = message.metadata.get("sender_uid") or message.metadata.get(
            "sender_address"
        )
        if isinstance(sender, str) and sender.strip():
            return f"auto:{sender.strip()}"
        return f"auto:{self.entity.uid}"

    def _persist_refs(self, session: Session, result: A2AMessageResult) -> None:
        changed = False
        if result.context_id and session.external_refs.get(_CONTEXT_ID_KEY) != result.context_id:
            session.external_refs[_CONTEXT_ID_KEY] = result.context_id
            changed = True
        if result.task_id and session.external_refs.get(_TASK_ID_KEY) != result.task_id:
            session.external_refs[_TASK_ID_KEY] = result.task_id
            changed = True
        if changed:
            session.updated_at = time.time()
            self._save_sessions()

    def _save_sessions(self) -> None:
        if not self.entity.sessions:
            return
        storage = get_storage_manager()
        sessions_dict = {
            sid: s.model_dump() for sid, s in self.entity.sessions.items()
        }
        storage.save_entity_sessions(self.entity.uid, sessions_dict)
