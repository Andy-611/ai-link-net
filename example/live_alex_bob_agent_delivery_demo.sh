#!/usr/bin/env bash
# Real contract + real agents live demo.
# The script only seeds instructions; Alex/Bob agents execute contract actions themselves.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${TRUST_DEMO_PORT:-18184}"
UI_PORT="${TRUST_DEMO_UI_PORT:-5199}"
HOST_NAME="${TRUST_DEMO_HOST:-alex-bob-agent-live}"
FP_HOME_DIR="${TRUST_DEMO_FP_HOME:-/tmp/aln-alex-bob-agent-live}"
STATE_FILE="${TRUST_DEMO_STATE_FILE:-${FP_HOME_DIR}/agent-demo-state.json}"
PYTHON="${ROOT_DIR}/.venv/bin/python"
ALN="${ROOT_DIR}/.venv/bin/aln"

mkdir -p "${FP_HOME_DIR}"

if [[ ! -x "${PYTHON}" || ! -x "${ALN}" ]]; then
  echo "Missing .venv runtime. Run: UV_CACHE_DIR=/tmp/uv-cache uv sync --extra dev"
  exit 1
fi

start_services() {
  FP_HOME="${FP_HOME_DIR}" "${ALN}" host stop --host "${HOST_NAME}" >/dev/null 2>&1 || true
  FP_HOME="${FP_HOME_DIR}" UV_CACHE_DIR=/tmp/uv-cache "${ALN}" host new \
    --name "${HOST_NAME}" \
    --bind-host 127.0.0.1 \
    --port "${PORT}" \
    >/dev/null

  "${PYTHON}" - <<PY
import time
import urllib.request

url = "http://127.0.0.1:${PORT}/health"
for _ in range(80):
    try:
        with urllib.request.urlopen(url, timeout=1):
            raise SystemExit(0)
    except Exception:
        time.sleep(0.25)
raise SystemExit("Host did not become healthy")
PY

  (
    cd "${ROOT_DIR}/aln/web"
    npm run dev -- --host 127.0.0.1 --port "${UI_PORT}"
  ) >/tmp/aln-alex-bob-agent-live-web.log 2>&1 &
}

start_services

TRUST_DEMO_PORT="${PORT}" \
TRUST_DEMO_UI_PORT="${UI_PORT}" \
TRUST_DEMO_FP_HOME="${FP_HOME_DIR}" \
TRUST_DEMO_STATE_FILE="${STATE_FILE}" \
TRUST_DEMO_ROOT="${ROOT_DIR}" \
"${PYTHON}" - <<'PY'
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = f"http://127.0.0.1:{os.environ['TRUST_DEMO_PORT']}/api/v1"
STATE_FILE = Path(os.environ["TRUST_DEMO_STATE_FILE"])
ROOT_DIR = os.environ["TRUST_DEMO_ROOT"]


def request(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc


def register(kind: str, name: str, description: str, **extra: object) -> dict:
    existing = request("GET", "/entities")["data"]
    for card in existing:
        if card["name"] == name and card["kind"] == kind:
            return card

    payload = {
        "kind": kind,
        "name": name,
        "is_public": True,
        "description": description,
    }
    payload.update(extra)
    return request("POST", "/entities", payload)["data"]


def get_contract(contract_id: str) -> dict:
    return request("GET", f"/trade/contracts/{contract_id}")["data"]


def send_director_prompt(
    director_uid: str,
    *,
    recipient_address: str,
    session_id: str,
    text: str,
) -> None:
    request("POST", "/messages/send", {
        "from_entity": director_uid,
        "to_address": recipient_address,
        "text": text,
        "session_id": session_id,
    })


def wait_for_contract(
    contract_id: str,
    *,
    expected_status: str | None = None,
    expected_last_action: str | None = None,
    require_rating: bool = False,
    timeout: float = 600.0,
) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        contract = get_contract(contract_id)
        status_ok = expected_status is None or contract["status"] == expected_status
        action_ok = expected_last_action is None or contract.get("last_action") == expected_last_action
        rating_ok = (not require_rating) or (contract.get("rating") is not None)
        if status_ok and action_ok and rating_ok:
            return contract
        time.sleep(2)
    raise TimeoutError(
        f"Contract {contract_id} did not reach status={expected_status} action={expected_last_action} within {timeout}s"
    )


def wait_for_structured_delivery(
    contract_id: str,
    *,
    expected_version: str | None = None,
    timeout: float = 600.0,
) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        contract = get_contract(contract_id)
        delivery = contract.get("current_delivery")
        costs = contract.get("current_execution_costs") or []
        if delivery:
            version_ok = expected_version is None or delivery.get("version") == expected_version
            artifacts_ok = len(delivery.get("artifacts") or []) > 0
            costs_ok = len(costs) > 0
            if version_ok and artifacts_ok and costs_ok:
                return contract
        time.sleep(2)
    raise TimeoutError(
        f"Contract {contract_id} did not record structured delivery/costs within {timeout}s"
    )


def wait_for_message(
    recipient_uid: str,
    *,
    sender_uid: str,
    session_id: str | None,
    seen_message_ids: set[str],
    timeout: float = 600.0,
) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        mailbox = request("GET", f"/messages/{recipient_uid}?limit=300")["data"]
        for message in mailbox:
            if message["message_id"] in seen_message_ids:
                continue
            sender = message.get("sender", "")
            if not sender.endswith(f":{sender_uid}"):
                continue
            payload = message.get("payload") or {}
            if session_id is not None and payload.get("session_id") != session_id:
                continue
            seen_message_ids.add(message["message_id"])
            return message
        time.sleep(2)
    raise TimeoutError(f"No message from {sender_uid} to {recipient_uid} in session {session_id} within {timeout}s")


def get_text(message: dict) -> str:
    payload = message.get("payload") or {}
    text = payload.get("text")
    return text if isinstance(text, str) else ""


def latest_created_contract(
    response: dict,
    *,
    title: str,
    party_a_address: str,
    party_b_address: str,
) -> dict:
    matches = [
        contract
        for contract in response["data"]["contracts"].values()
        if contract["title"] == title
        and contract["party_a"]["address"] == party_a_address
        and contract["party_b"]["address"] == party_b_address
    ]
    if not matches:
        raise RuntimeError(f"No contract returned for title={title}")
    return max(matches, key=lambda contract: contract.get("created_at", 0))


director = register(
    "human",
    "Director",
    "Hidden demo coordinator that seeds tasks for the agents.",
)
arbiter = register(
    "arbiter",
    "Arbiter",
    "Reviews every contract transition and signs trusted snapshots.",
)
alex = register(
    "agent",
    "Alex",
    "Product owner agent. Creates outsourcing scope, reviews delivery, requests rework, accepts good work, and rates the result.",
    provider="codex",
    workdir=ROOT_DIR,
)
bob = register(
    "agent",
    "Bob",
    "Software delivery agent. Implements outsourced work, sends progress updates, and advances the contract when work is ready.",
    provider="codex",
    workdir=ROOT_DIR,
)

create_response = request("POST", "/trade/send", {
    "from_entity": alex["entity_uid"],
    "kind": "contract_create",
    "payload": {
        "party_a": {"address": alex["address"]["address"]},
        "party_b": {"address": bob["address"]["address"]},
        "party_a_card": alex,
        "party_b_card": bob,
        "title": "Vendor Portal MVP Outsourcing Delivery",
        "description": (
            "Bob delivers a vendor portal MVP for Alex in multiple versions. "
            "Use the linked work session for real collaboration while Arbiter signs every trust snapshot."
        ),
        "amount": 300,
        "funding_mode": "direct",
    },
})
contract = latest_created_contract(
    create_response,
    title="Vendor Portal MVP Outsourcing Delivery",
    party_a_address=alex["address"]["address"],
    party_b_address=bob["address"]["address"],
)
contract_id = contract["contract_id"]
work_session_id = contract["work_session_id"]
director_to_bob_session = f"director:{contract_id}:bob"
director_to_alex_session = f"director:{contract_id}:alex"

seen_message_ids: set[str] = set()

request("POST", f"/trade/contracts/{contract_id}/messages", {
    "from_entity": alex["entity_uid"],
    "text": (
        "Kickoff for this outsourcing contract: we will use this linked work session for planning, delivery notes, "
        "rework discussion, and final closure. Start by reviewing the contract and then reply here with your initial plan."
    ),
})

send_director_prompt(
    director["entity_uid"],
    recipient_address=bob["address"]["address"],
    session_id=director_to_bob_session,
    text=(
        f"You are Bob on contract {contract_id}. First inspect the contract and approve it now with "
        f"`aln contract approve -e {bob['address']['address']} --id {contract_id}`. "
        "Then send Alex a short work plan via `aln mail` in your existing contract work conversation. "
        "Keep the note concise and do not submit delivery yet."
    ),
)
contract = wait_for_contract(contract_id, expected_status="active")
reply_v1_plan = wait_for_message(
    alex["entity_uid"],
    sender_uid=bob["entity_uid"],
    session_id=work_session_id,
    seen_message_ids=seen_message_ids,
)

send_director_prompt(
    director["entity_uid"],
    recipient_address=bob["address"]["address"],
    session_id=director_to_bob_session,
    text=(
        f"Now advance contract {contract_id} as the v1 delivery. "
        f"Run `aln contract complete -e {bob['address']['address']} --id {contract_id} "
        "--reason \"Delivery v1: login, vendor list, and the first contract detail screen are ready for review.\" "
        "--delivery-version v1.0.0 "
        "--delivery-summary \"Vendor portal MVP first delivery with login, vendor list, and base contract detail view.\" "
        "--artifact \"preview|https://preview.example/vendor-portal/v1|Preview v1\" "
        "--artifact \"commit|git://ai-link-net/commit/v1-base|Commit v1-base|sha256:v1-base\" "
        "--cost-provider codex "
        "--cost-model gpt-5-codex "
        "--cost-phase implementation "
        "--input-tokens 1200 "
        "--output-tokens 450 "
        "--cost-usd 0.37 "
        "--runtime-ms 182000 "
        "--cost-notes \"Initial implementation delivery turn\"` "
        "Wait for Arbiter to move the contract into review before you do anything else. "
        "Do not send a simplified fallback complete without the structured delivery and cost fields. "
        "Then send Alex a short delivery note in your existing work conversation summarizing what is ready."
    ),
)
contract = wait_for_contract(contract_id, expected_status="completing")
contract = wait_for_structured_delivery(contract_id, expected_version="v1.0.0")
reply_v1_delivery = wait_for_message(
    alex["entity_uid"],
    sender_uid=bob["entity_uid"],
    session_id=work_session_id,
    seen_message_ids=seen_message_ids,
)

send_director_prompt(
    director["entity_uid"],
    recipient_address=alex["address"]["address"],
    session_id=director_to_alex_session,
    text=(
        f"You are Alex reviewing contract {contract_id}. "
        "Treat this as an incomplete v1 because trust evidence is still missing. "
        f"Run `aln contract rework -e {alex['address']['address']} --id {contract_id} --reason "
        "\"Please add trust evidence to the contract detail view: snapshot chain, approvals, and Arbiter attestation.\"` "
        "Then send Bob a concise rework note in your existing work conversation. Do not accept yet."
    ),
)
contract = wait_for_contract(contract_id, expected_status="active")
reply_rework = wait_for_message(
    bob["entity_uid"],
    sender_uid=alex["entity_uid"],
    session_id=work_session_id,
    seen_message_ids=seen_message_ids,
)

send_director_prompt(
    director["entity_uid"],
    recipient_address=bob["address"]["address"],
    session_id=director_to_bob_session,
    text=(
        f"Address Alex's rework on contract {contract_id}. "
        f"When ready, run `aln contract complete -e {bob['address']['address']} --id {contract_id} "
        "--reason \"Delivery v2: trust evidence panel, signed snapshot chain, and approval review are added.\" "
        "--delivery-version v2.0.0 "
        "--delivery-summary \"Second delivery adds trust evidence, signed snapshot chain, approval review, and Arbiter attestation context.\" "
        "--artifact \"preview|https://preview.example/vendor-portal/v2|Preview v2\" "
        "--artifact \"commit|git://ai-link-net/commit/v2-trust|Commit v2-trust|sha256:v2-trust\" "
        "--cost-provider codex "
        "--cost-model gpt-5-codex "
        "--cost-phase rework "
        "--input-tokens 900 "
        "--output-tokens 320 "
        "--cost-usd 0.24 "
        "--runtime-ms 133000 "
        "--cost-notes \"Rework delivery with trust evidence\"` "
        "Wait for Arbiter to move the contract into review before you do anything else. "
        "Do not send a simplified fallback complete without the structured delivery and cost fields. "
        "Then send Alex a concise v2 delivery note in the same work conversation."
    ),
)
contract = wait_for_contract(contract_id, expected_status="completing")
contract = wait_for_structured_delivery(contract_id, expected_version="v2.0.0")
reply_v2_delivery = wait_for_message(
    alex["entity_uid"],
    sender_uid=bob["entity_uid"],
    session_id=work_session_id,
    seen_message_ids=seen_message_ids,
)

send_director_prompt(
    director["entity_uid"],
    recipient_address=alex["address"]["address"],
    session_id=director_to_alex_session,
    text=(
        f"Review Bob's v2 on contract {contract_id}. If it is acceptable, run "
        f"`aln contract accept -e {alex['address']['address']} --id {contract_id} --reason "
        "\"Alex accepts v2 as the final outsourced delivery.\"` "
        f"and then run `aln contract rate -e {alex['address']['address']} --id {contract_id} --rating 5 --review "
        "\"Real work messages stayed linked to the same contract session, and the signed trust chain is clear.\"`. "
        "After both actions, send Bob a short closing note in the same work conversation."
    ),
)
contract = wait_for_contract(contract_id, expected_status="settling", require_rating=True)
reply_close = wait_for_message(
    bob["entity_uid"],
    sender_uid=alex["entity_uid"],
    session_id=work_session_id,
    seen_message_ids=seen_message_ids,
)

summary = {
    "host_url": f"http://127.0.0.1:{os.environ['TRUST_DEMO_PORT']}",
    "web_url_for_alex": (
        f"http://127.0.0.1:{os.environ['TRUST_DEMO_UI_PORT']}/"
        f"?entity_uid={alex['entity_uid']}&host_url=http%3A//127.0.0.1%3A{os.environ['TRUST_DEMO_PORT']}"
    ),
    "web_url_for_bob": (
        f"http://127.0.0.1:{os.environ['TRUST_DEMO_UI_PORT']}/"
        f"?entity_uid={bob['entity_uid']}&host_url=http%3A//127.0.0.1%3A{os.environ['TRUST_DEMO_PORT']}"
    ),
    "contract_id": contract_id,
    "work_session_id": work_session_id,
    "status": contract["status"],
    "snapshot_history_count": len(contract.get("snapshot_history") or []),
    "rating": contract.get("rating"),
    "reply_v1_plan": get_text(reply_v1_plan),
    "reply_v1_delivery": get_text(reply_v1_delivery),
    "reply_rework": get_text(reply_rework),
    "reply_v2_delivery": get_text(reply_v2_delivery),
    "reply_close": get_text(reply_close),
}

STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
STATE_FILE.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(summary, indent=2, ensure_ascii=False))
PY
