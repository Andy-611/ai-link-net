#!/usr/bin/env bash
# Step-by-step Trade & Trust live demo.
# Usage:
#   demo/live_alex_bob_step_demo.sh setup
#   demo/live_alex_bob_step_demo.sh create
#   demo/live_alex_bob_step_demo.sh approve
#   demo/live_alex_bob_step_demo.sh deliver_v1
#   demo/live_alex_bob_step_demo.sh rework
#   demo/live_alex_bob_step_demo.sh deliver_v2
#   demo/live_alex_bob_step_demo.sh accept
#   demo/live_alex_bob_step_demo.sh rate

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STEP="${1:-setup}"
PORT="${TRUST_DEMO_PORT:-18179}"
UI_PORT="${TRUST_DEMO_UI_PORT:-5194}"
HOST_NAME="${TRUST_DEMO_HOST:-alex-bob-step-demo}"
FP_HOME_DIR="${TRUST_DEMO_FP_HOME:-/tmp/aln-alex-bob-step-demo}"
STATE_FILE="${TRUST_DEMO_STATE_FILE:-${FP_HOME_DIR}/demo-step-state.json}"

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
for _ in range(60):
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
  ) >/tmp/aln-alex-bob-step-web.log 2>&1 &
}

if [[ "${STEP}" == "setup" ]]; then
  start_services
fi

TRUST_DEMO_PORT="${PORT}" \
TRUST_DEMO_UI_PORT="${UI_PORT}" \
TRUST_DEMO_STATE_FILE="${STATE_FILE}" \
TRUST_DEMO_STEP="${STEP}" \
"${PYTHON}" - <<'PY'
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = f"http://127.0.0.1:{os.environ['TRUST_DEMO_PORT']}/api/v1"
STEP = os.environ["TRUST_DEMO_STEP"]
STATE_FILE = Path(os.environ["TRUST_DEMO_STATE_FILE"])


def request(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc


def register(kind: str, name: str, description: str) -> dict:
    existing = request("GET", "/entities")["data"]
    for card in existing:
        if card["name"] == name and card["kind"] == kind:
            return card
    return request("POST", "/entities", {
        "kind": kind,
        "name": name,
        "is_public": True,
        "description": description,
    })["data"]


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def get_contract(contract_id: str) -> dict:
    return request("GET", f"/trade/contracts/{contract_id}")["data"]


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


def action_payload(contract: dict, **extra: object) -> dict:
    payload = {
        "contract_id": contract["contract_id"],
        "expected_status": contract["status"],
        "revision": contract["draft_version"],
        "terms_hash": contract["terms_hash"],
        "source_snapshot_hash": contract["current_snapshot_hash"],
    }
    payload.update(extra)
    return payload


state = load_state()
state["port"] = os.environ["TRUST_DEMO_PORT"]
state["ui_port"] = os.environ["TRUST_DEMO_UI_PORT"]

arbiter = register("arbiter", "Arbiter", "Reviews every contract transition and signs trusted snapshots")
alex = register("human", "Alex", "Creates a task and reviews Bob's delivery")
bob = register("human", "Bob", "Accepts the task and iterates on delivery")

state["participants"] = {
    "alex": alex,
    "bob": bob,
    "arbiter": arbiter,
}

if STEP == "setup":
    save_state(state)
elif STEP == "create":
    response = request("POST", "/trade/send", {
        "from_entity": "Alex",
        "kind": "contract_create",
        "payload": {
            "party_a": {"address": alex["address"]["address"]},
            "party_b": {"address": bob["address"]["address"]},
            "party_a_card": alex,
            "party_b_card": bob,
            "title": "Vendor Portal MVP Outsourcing Delivery",
            "description": (
                "Bob will deliver a vendor portal MVP for Alex in multiple versions. "
                "The contract should be advanced step by step, not preloaded."
            ),
            "amount": 300,
            "funding_mode": "direct",
        },
    })
    contract = latest_created_contract(
        response,
        title="Vendor Portal MVP Outsourcing Delivery",
        party_a_address=alex["address"]["address"],
        party_b_address=bob["address"]["address"],
    )
    state["contract_id"] = contract["contract_id"]
    state["last_step"] = "create"
    save_state(state)
elif STEP in {"approve", "deliver_v1", "rework", "deliver_v2", "accept", "rate"}:
    contract_id = state.get("contract_id")
    if not contract_id:
      raise SystemExit("No contract yet. Run setup then create first.")
    contract = get_contract(contract_id)
    if STEP == "approve":
        request("POST", "/trade/send", {
            "from_entity": "Bob",
            "kind": "contract_approve",
            "payload": action_payload(contract),
        })
    elif STEP == "deliver_v1":
        request("POST", "/trade/send", {
                "from_entity": "Bob",
                "kind": "contract_complete",
                "payload": action_payload(
                    contract,
                    reason="Delivery v1: login, project list, and base contract detail page are ready.",
                ),
            })
    elif STEP == "rework":
        request("POST", "/trade/send", {
                "from_entity": "Alex",
                "kind": "contract_rework",
                "payload": action_payload(
                    contract,
                    reason="Please add trust evidence for review: snapshot chain, approvals, and Arbiter attestation.",
                ),
            })
    elif STEP == "deliver_v2":
        request("POST", "/trade/send", {
                "from_entity": "Bob",
                "kind": "contract_complete",
                "payload": action_payload(
                    contract,
                    reason="Delivery v2: trust review view, signed snapshot chain, and approval evidence are added.",
                ),
            })
    elif STEP == "accept":
        request("POST", "/trade/send", {
                "from_entity": "Alex",
                "kind": "contract_accept",
                "payload": action_payload(
                    contract,
                    reason="Alex accepts v2 as the final outsourced delivery.",
                ),
            })
    elif STEP == "rate":
        request("POST", "/trade/send", {
            "from_entity": "Alex",
            "kind": "contract_rate",
                "payload": action_payload(
                    contract,
                    rating=5,
                    review="Clear delivery history, clean rework loop, and auditable trust evidence.",
                ),
            })
    state["last_step"] = STEP
    save_state(state)
else:
    raise SystemExit(f"Unknown step: {STEP}")

contract = get_contract(state["contract_id"]) if state.get("contract_id") else None
alex_uid = alex["entity_uid"]
web_url = (
    f"http://127.0.0.1:{os.environ['TRUST_DEMO_UI_PORT']}/"
    f"?entity_uid={alex_uid}&host_url=http%3A//127.0.0.1%3A{os.environ['TRUST_DEMO_PORT']}"
)

print(json.dumps({
    "step": STEP,
    "web_url_for_alex": web_url,
    "web_url_for_bob": (
        f"http://127.0.0.1:{os.environ['TRUST_DEMO_UI_PORT']}/"
        f"?entity_uid={bob['entity_uid']}&host_url=http%3A//127.0.0.1%3A{os.environ['TRUST_DEMO_PORT']}"
    ),
    "contract_id": state.get("contract_id"),
    "status": None if contract is None else contract["status"],
    "current_snapshot_hash": None if contract is None else contract["current_snapshot_hash"],
    "last_step": state.get("last_step"),
}, indent=2, ensure_ascii=False))
PY
