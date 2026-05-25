"""A2A v1.0 client adapter — connects FP entities to external A2A agents (outbound)."""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, Field

# ── Wire-level constants (A2A v1.0, ProtoJSON) ──────────────────────
_AGENT_CARD_PATH = "/.well-known/agent-card.json"
_A2A_VERSION_HEADER = "A2A-Version"
_PROTOCOL_VERSION = "1.0"
_JSONRPC_BINDING = "JSONRPC"
_ROLE_USER = "ROLE_USER"
_TERMINAL_TASK_STATES = frozenset({
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_REJECTED",
})
_ERROR_TASK_STATES = frozenset({
    "TASK_STATE_FAILED",
    "TASK_STATE_REJECTED",
})


class A2AAgentConfig(BaseModel):
    """Connection config stored in entity.metadata['a2a_config']."""

    url: str
    api_key: str | None = None
    api_key_header: str = "X-API-Key"
    auth_bearer: str | None = None
    protocol_version: str = _PROTOCOL_VERSION
    poll_interval: float = 1.0
    poll_timeout: float = 60.0


class A2ASkill(BaseModel):
    """One skill advertised in AgentCard."""

    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class A2AInterface(BaseModel):
    """One supportedInterfaces entry — protocol binding offered by the agent."""

    url: str
    protocol_binding: str
    protocol_version: str


class A2AAgentCard(BaseModel):
    """Subset of v1.0 AgentCard fields consumed by this adapter."""

    name: str
    description: str = ""
    version: str = ""
    supported_interfaces: list[A2AInterface] = Field(default_factory=list)
    skills: list[A2ASkill] = Field(default_factory=list)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class A2AMessageResult(BaseModel):
    """Normalized outcome of SendMessage (post-polling if a Task was returned)."""

    text: str
    context_id: str | None = None
    task_id: str | None = None
    state: str | None = None
    is_error: bool = False


class A2AClient(ABC):
    """Abstract client speaking A2A protocol to an external agent."""

    @abstractmethod
    async def send_message(
        self,
        text: str,
        *,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> A2AMessageResult:
        """Send one text message; block until terminal Task state or message response."""

    @abstractmethod
    async def fetch_agent_card(self) -> A2AAgentCard:
        """GET /.well-known/agent-card.json and return parsed card."""

    @abstractmethod
    async def get_task(self, task_id: str) -> A2AMessageResult:
        """Fetch current task state — used for polling and explicit lookups."""


class HttpA2AClient(A2AClient):
    """JSON-RPC over HTTP client for A2A v1.0.

    On first use, fetches the AgentCard to discover the JSON-RPC endpoint from
    supported_interfaces; thereafter posts SendMessage and polls GetTask until
    the task reaches a terminal state or the configured timeout elapses.
    """

    def __init__(self, config: A2AAgentConfig) -> None:
        self._config = config
        self._base_url = config.url.rstrip("/")
        self._rpc_url: str | None = None
        self._agent_card: A2AAgentCard | None = None

    async def fetch_agent_card(self) -> A2AAgentCard:
        if self._agent_card is not None:
            return self._agent_card
        url = self._base_url + _AGENT_CARD_PATH
        raw = await asyncio.to_thread(self._http_get_json, url)
        self._agent_card = self._parse_agent_card(raw)
        return self._agent_card

    async def send_message(
        self,
        text: str,
        *,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> A2AMessageResult:
        rpc_url = await self._ensure_rpc_url()
        message_obj: dict[str, Any] = {
            "messageId": uuid4().hex,
            "role": _ROLE_USER,
            "parts": [{"text": text}],
        }
        if context_id:
            message_obj["contextId"] = context_id
        if task_id:
            message_obj["taskId"] = task_id

        response = await asyncio.to_thread(
            self._post_rpc, rpc_url, "SendMessage", {"message": message_obj}
        )
        result = response.get("result") or {}
        if "message" in result:
            return self._normalize_message_result(result["message"])
        if "task" in result:
            return await self._resolve_task_result(result["task"], rpc_url)
        return A2AMessageResult(text="", is_error=True)

    async def get_task(self, task_id: str) -> A2AMessageResult:
        rpc_url = await self._ensure_rpc_url()
        response = await asyncio.to_thread(
            self._post_rpc, rpc_url, "GetTask", {"id": task_id}
        )
        task = response.get("result") or {}
        return self._normalize_task_result(task)

    # ── internals ───────────────────────────────────────────────────

    async def _ensure_rpc_url(self) -> str:
        if self._rpc_url is not None:
            return self._rpc_url
        card = await self.fetch_agent_card()
        for iface in card.supported_interfaces:
            if (
                iface.protocol_binding == _JSONRPC_BINDING
                and iface.protocol_version == self._config.protocol_version
            ):
                self._rpc_url = iface.url
                logger.debug(
                    f"[HttpA2AClient] selected JSON-RPC endpoint: {self._rpc_url}"
                )
                return self._rpc_url
        raise ValueError(
            f"AgentCard at {self._base_url} exposes no JSON-RPC "
            f"interface for protocol_version={self._config.protocol_version}"
        )

    async def _resolve_task_result(
        self, task: dict[str, Any], rpc_url: str
    ) -> A2AMessageResult:
        state = self._task_state(task)
        if state in _TERMINAL_TASK_STATES:
            return self._normalize_task_result(task)
        deadline = time.monotonic() + self._config.poll_timeout
        task_id = task.get("id")
        if not task_id:
            return A2AMessageResult(text="", state=state, is_error=True)
        while time.monotonic() < deadline:
            await asyncio.sleep(self._config.poll_interval)
            response = await asyncio.to_thread(
                self._post_rpc, rpc_url, "GetTask", {"id": task_id}
            )
            current = response.get("result") or {}
            if self._task_state(current) in _TERMINAL_TASK_STATES:
                return self._normalize_task_result(current)
        logger.warning(
            f"[HttpA2AClient] task {task_id} did not reach terminal state "
            f"within {self._config.poll_timeout}s"
        )
        return A2AMessageResult(
            text="", task_id=task_id, state=state, is_error=True
        )

    def _normalize_message_result(self, msg: dict[str, Any]) -> A2AMessageResult:
        return A2AMessageResult(
            text=self._extract_text_from_parts(msg.get("parts")),
            context_id=msg.get("contextId"),
            task_id=msg.get("taskId"),
        )

    def _normalize_task_result(self, task: dict[str, Any]) -> A2AMessageResult:
        state = self._task_state(task)
        return A2AMessageResult(
            text=self._extract_text_from_task(task),
            context_id=task.get("contextId"),
            task_id=task.get("id"),
            state=state,
            is_error=state in _ERROR_TASK_STATES,
        )

    @staticmethod
    def _task_state(task: dict[str, Any]) -> str:
        status = task.get("status") if isinstance(task, dict) else None
        if isinstance(status, dict):
            state = status.get("state")
            if isinstance(state, str):
                return state
        return ""

    @staticmethod
    def _extract_text_from_parts(parts: Any) -> str:
        if not isinstance(parts, list):
            return ""
        chunks = [p.get("text") for p in parts if isinstance(p, dict) and p.get("text")]
        return "\n".join(chunks)

    @classmethod
    def _extract_text_from_task(cls, task: dict[str, Any]) -> str:
        status = task.get("status") if isinstance(task, dict) else None
        if isinstance(status, dict):
            status_msg = status.get("message")
            if isinstance(status_msg, dict):
                text = cls._extract_text_from_parts(status_msg.get("parts"))
                if text:
                    return text
        artifacts = task.get("artifacts")
        if isinstance(artifacts, list):
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    continue
                text = cls._extract_text_from_parts(artifact.get("parts"))
                if text:
                    return text
        return ""

    @staticmethod
    def _parse_agent_card(raw: dict[str, Any]) -> A2AAgentCard:
        interfaces_raw = raw.get("supportedInterfaces") or []
        interfaces = [
            A2AInterface(
                url=item.get("url", ""),
                protocol_binding=item.get("protocolBinding", ""),
                protocol_version=item.get("protocolVersion", ""),
            )
            for item in interfaces_raw
            if isinstance(item, dict)
        ]
        skills_raw = raw.get("skills") or []
        skills = [
            A2ASkill(
                id=item.get("id", ""),
                name=item.get("name", ""),
                description=item.get("description", ""),
                tags=list(item.get("tags") or []),
            )
            for item in skills_raw
            if isinstance(item, dict)
        ]
        return A2AAgentCard(
            name=raw.get("name", ""),
            description=raw.get("description", ""),
            version=raw.get("version", ""),
            supported_interfaces=interfaces,
            skills=skills,
            capabilities=raw.get("capabilities") or {},
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            _A2A_VERSION_HEADER: self._config.protocol_version,
        }
        if self._config.api_key:
            headers[self._config.api_key_header] = self._config.api_key
        if self._config.auth_bearer:
            headers["Authorization"] = f"Bearer {self._config.auth_bearer}"
        return headers

    def _http_get_json(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(url, headers=self._build_headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"GET {url} → HTTP {e.code}: {e.read().decode(errors='replace')}") from e

    def _post_rpc(self, url: str, method: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": uuid4().hex,
            "method": method,
            "params": params,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers=self._build_headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                response = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"POST {url} {method} → HTTP {e.code}: {e.read().decode(errors='replace')}"
            ) from e
        if isinstance(response, dict) and response.get("error"):
            err = response["error"]
            raise RuntimeError(
                f"A2A JSON-RPC error {err.get('code')}: {err.get('message')}"
            )
        return response if isinstance(response, dict) else {}


def create_a2a_client(config: A2AAgentConfig) -> A2AClient:
    """Factory mirroring create_mcp_client."""
    logger.debug(f"Creating HttpA2AClient: url={config.url}")
    return HttpA2AClient(config)
