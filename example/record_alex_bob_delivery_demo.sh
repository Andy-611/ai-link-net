#!/usr/bin/env bash
# Record the design-doc Trade & Trust demo:
# Alex creates a task, Bob accepts, Arbiter reviews every transition, and the
# two parties continue collaboration through signed contract snapshots.
#
# Output:
#   demo/recordings/alex-bob-delivery-<timestamp>/
#     terminal.cast     Asciinema terminal recording, when asciinema is installed
#     terminal.log      Full terminal transcript
#     summary.json      Scenario summary and URLs
#     timeline.md       Human-readable snapshot chain
#     contract.json     Final contract JSON from the Trade API

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
PORT="${TRUST_DEMO_PORT:-18161}"
UI_PORT="${TRUST_DEMO_UI_PORT:-5176}"
HOST_NAME="${TRUST_DEMO_HOST:-alex-bob-delivery}"
FP_HOME_DIR="${TRUST_DEMO_FP_HOME:-/tmp/aln-alex-bob-delivery-${STAMP}}"
OUT_DIR="${TRUST_DEMO_OUT_DIR:-${ROOT_DIR}/demo/recordings/alex-bob-delivery-${STAMP}}"
CAST_FILE="${OUT_DIR}/terminal.cast"
LOG_FILE="${OUT_DIR}/terminal.log"
SUMMARY_FILE="${OUT_DIR}/summary.json"
TIMELINE_FILE="${OUT_DIR}/timeline.md"
CONTRACT_FILE="${OUT_DIR}/contract.json"

mkdir -p "${OUT_DIR}"

if [[ "${TRUST_DEMO_NO_ASCIINEMA:-0}" != "1" && -z "${ASCIINEMA_SESSION:-}" ]] && command -v asciinema >/dev/null 2>&1; then
  echo "Recording Alex/Bob delivery demo with asciinema..."
  echo "output: ${CAST_FILE}"
  TRUST_DEMO_NO_ASCIINEMA=1 \
  TRUST_DEMO_OUT_DIR="${OUT_DIR}" \
  TRUST_DEMO_FP_HOME="${FP_HOME_DIR}" \
  asciinema record \
    --overwrite \
    --idle-time-limit 1 \
    --title "Alex/Bob Trade & Trust Delivery Demo" \
    --command "bash ${BASH_SOURCE[0]}" \
    "${CAST_FILE}"
  echo
  echo "Asciinema recording saved: ${CAST_FILE}"
  echo "Recording artifacts:"
  echo "  ${LOG_FILE}"
  echo "  ${SUMMARY_FILE}"
  echo "  ${TIMELINE_FILE}"
  echo "  ${CONTRACT_FILE}"
  exit 0
fi

exec > >(tee "${LOG_FILE}") 2>&1

cd "${ROOT_DIR}"

PYTHON="${ROOT_DIR}/.venv/bin/python"
ALN="${ROOT_DIR}/.venv/bin/aln"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Missing .venv Python. Run: UV_CACHE_DIR=/tmp/uv-cache uv sync --extra dev"
  exit 1
fi

if [[ ! -x "${ALN}" ]]; then
  echo "Missing aln CLI in .venv. Run: UV_CACHE_DIR=/tmp/uv-cache uv sync --extra dev"
  exit 1
fi

echo "========== Alex/Bob Trade & Trust Delivery Demo =========="
echo "repo: ${ROOT_DIR}"
echo "fp_home: ${FP_HOME_DIR}"
echo "host: ${HOST_NAME}"
echo "port: ${PORT}"
echo "output: ${OUT_DIR}"
echo "asciinema_cast: ${CAST_FILE}"
echo "keep_host: ${KEEP_TRUST_DEMO_HOST:-0}"
echo "start_web_ui: ${START_TRUST_DEMO_UI:-0}"
echo

cleanup() {
  if [[ "${KEEP_TRUST_DEMO_HOST:-0}" == "1" ]]; then
    echo
    echo "KEEP_TRUST_DEMO_HOST=1, leaving demo host running."
    return
  fi
  echo
  echo "Stopping demo host..."
  FP_HOME="${FP_HOME_DIR}" "${ALN}" host stop --host "${HOST_NAME}" >/dev/null 2>&1 || true
  if [[ -n "${UI_PID:-}" ]] && kill -0 "${UI_PID}" >/dev/null 2>&1; then
    echo "Stopping Web UI PID ${UI_PID}..."
    kill "${UI_PID}" >/dev/null 2>&1 || true
    wait "${UI_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "1. Start isolated host"
FP_HOME="${FP_HOME_DIR}" "${ALN}" host stop --host "${HOST_NAME}" >/dev/null 2>&1 || true
FP_HOME="${FP_HOME_DIR}" UV_CACHE_DIR=/tmp/uv-cache "${ALN}" host new \
  --name "${HOST_NAME}" \
  --bind-host 127.0.0.1 \
  --port "${PORT}" \
 

echo
echo "2. Wait for host health"
"${PYTHON}" - <<PY
import time
import urllib.request

url = "http://127.0.0.1:${PORT}/health"
last_error = None
for _ in range(60):
    try:
        with urllib.request.urlopen(url, timeout=1) as resp:
            print(resp.read().decode("utf-8"))
            raise SystemExit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(0.25)
raise SystemExit(f"Host did not become healthy: {last_error}")
PY

echo
if [[ "${START_TRUST_DEMO_UI:-0}" == "1" ]]; then
  echo "3. Start Web UI for visual inspection"
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm not found; skipping Web UI startup"
  elif [[ ! -d "${ROOT_DIR}/aln/web/node_modules" ]]; then
    echo "aln/web/node_modules not found; run npm install in aln/web first"
  else
    (
      cd "${ROOT_DIR}/aln/web"
      npm run dev -- --host 127.0.0.1 --port "${UI_PORT}"
    ) >/dev/null 2>&1 &
    UI_PID=$!
    echo "web_ui_pid: ${UI_PID}"
    echo "web_ui_base: http://localhost:${UI_PORT}"
  fi
  echo
fi

echo "3. Run Alex/Bob multi-snapshot delivery flow"
TRUST_DEMO_PORT="${PORT}" \
TRUST_DEMO_UI_PORT="${UI_PORT}" \
TRUST_SUMMARY_FILE="${SUMMARY_FILE}" \
TRUST_TIMELINE_FILE="${TIMELINE_FILE}" \
TRUST_CONTRACT_FILE="${CONTRACT_FILE}" \
"${PYTHON}" - <<'PY'
import json
import os
import urllib.error
import urllib.request

from fp.trade.hashing import verify_attestation
from fp.trade.models import Contract

BASE = f"http://127.0.0.1:{os.environ['TRUST_DEMO_PORT']}/api/v1"
SUMMARY_FILE = os.environ["TRUST_SUMMARY_FILE"]
TIMELINE_FILE = os.environ["TRUST_TIMELINE_FILE"]
CONTRACT_FILE = os.environ["TRUST_CONTRACT_FILE"]


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


def short_hash(value: str | None) -> str:
    return "-" if not value else value[:12]


def delivery_payload(
    *,
    contract_id: str,
    version: str,
    summary: str,
    produced_by: str,
    source_session_id: str,
    source_message_id: str,
    artifacts: list[dict],
    produced_at: float,
) -> dict:
    return {
        "delivery_id": f"{contract_id}-{version}",
        "version": version,
        "summary": summary,
        "artifacts": artifacts,
        "source_session_id": source_session_id,
        "source_message_id": source_message_id,
        "produced_by": {"address": produced_by},
        "produced_at": produced_at,
    }


def cost_payload(
    *,
    contract_id: str,
    actor_address: str,
    phase: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    runtime_ms: int,
    notes: str,
    recorded_at: float,
) -> list[dict]:
    return [{
        "report_id": f"{contract_id}-cost-{phase}",
        "actor": {"address": actor_address},
        "phase": phase,
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "runtime_ms": runtime_ms,
        "notes": notes,
        "recorded_at": recorded_at,
    }]


def validate_attestation(contract_json: dict) -> bool:
    contract = Contract.model_validate(contract_json)
    arbiter_snapshot = next(p for p in contract.participant_snapshots if p.role == "arbiter")
    return verify_attestation(contract.to_snapshot(), arbiter_snapshot.sign_public_key)


timeline: list[dict] = []


def capture(
    label: str,
    actor: str,
    message: str,
    contract_json: dict,
    source_snapshot_hash: str | None,
    previous_snapshot_hash: str | None,
) -> None:
    attestation = contract_json.get("attestation") or {}
    timeline.append({
        "label": label,
        "actor": actor,
        "message": message,
        "status": contract_json["status"],
        "revision": contract_json["draft_version"],
        "source_snapshot_hash_used": source_snapshot_hash,
        "snapshot_hash": contract_json["current_snapshot_hash"],
        "prev_snapshot_hash": contract_json["prev_snapshot_hash"],
        "prev_links_to_previous_step": (
            previous_snapshot_hash is None
            or contract_json["prev_snapshot_hash"] == previous_snapshot_hash
        ),
        "attestation_snapshot_hash_matches": (
            attestation.get("snapshot_hash") == contract_json["current_snapshot_hash"]
        ),
        "attestation_valid": validate_attestation(contract_json),
        "terms_hash": contract_json["terms_hash"],
        "approvals": [
            [
                a["party_role"],
                a["approved_revision"],
                a["approved_terms_hash"] == contract_json["terms_hash"],
            ]
            for a in contract_json.get("approvals", [])
        ],
        "last_action": contract_json.get("last_action"),
        "last_actor": (contract_json.get("last_actor") or {}).get("address"),
        "last_reason": contract_json.get("last_reason"),
        "rework_count": contract_json.get("rework_count"),
    })


def contract_action(
    *,
    actor: str,
    kind: str,
    contract_json: dict,
    reason: str | None = None,
    rating: int | None = None,
    review: str | None = None,
    extra_payload: dict | None = None,
) -> dict:
    payload: dict = {
        "contract_id": contract_json["contract_id"],
        "expected_status": contract_json["status"],
        "revision": contract_json["draft_version"],
        "terms_hash": contract_json["terms_hash"],
        "source_snapshot_hash": contract_json["current_snapshot_hash"],
    }
    if reason is not None:
        payload["reason"] = reason
    if rating is not None:
        payload["rating"] = rating
    if review is not None:
        payload["review"] = review
    if extra_payload:
        payload.update(extra_payload)
    request("POST", "/trade/send", {
        "from_entity": actor,
        "kind": kind,
        "payload": payload,
    })
    return get_contract(contract_json["contract_id"])


arbiter = register("arbiter", "Arbiter", "Reviews every contract transition and signs trusted snapshots")
alex = register("human", "Alex", "Creates a task and reviews Bob's delivery")
bob = register("human", "Bob", "Accepts the task and iterates on delivery")

print("participants:")
print(f"  Alex={alex['address']['address']}")
print(f"  Bob={bob['address']['address']}")
print(f"  Arbiter={arbiter['address']['address']}")

create = request("POST", "/trade/send", {
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
            "Alex may request rework, and every collaboration step must reference "
            "the latest signed contract snapshot."
        ),
        "amount": 300,
        "funding_mode": "direct",
    },
})
contract = latest_created_contract(
    create,
    title="Vendor Portal MVP Outsourcing Delivery",
    party_a_address=alex["address"]["address"],
    party_b_address=bob["address"]["address"],
)
capture("S0_CREATE", "Alex", "Alex creates the task contract; Arbiter freezes participant snapshots and signs S0.", contract, None, None)
print(f"S0_CREATE: status={contract['status']} snapshot={short_hash(contract['current_snapshot_hash'])}")

previous_hash = contract["current_snapshot_hash"]
contract = contract_action(actor="Bob", kind="contract_approve", contract_json=contract)
capture("S1_ACCEPT", "Bob", "Bob accepts the task using S0 as source_snapshot_hash; Arbiter checks role/status/terms and signs S1.", contract, previous_hash, previous_hash)
print(f"S1_ACCEPT: status={contract['status']} source={short_hash(previous_hash)} snapshot={short_hash(contract['current_snapshot_hash'])}")

previous_hash = contract["current_snapshot_hash"]
contract = contract_action(
    actor="Bob",
    kind="contract_complete",
    contract_json=contract,
    reason="Delivery v1: login, project list, and base contract detail page are ready.",
    extra_payload={
        "delivery": delivery_payload(
            contract_id=contract["contract_id"],
            version="v1.0.0",
            summary="Vendor portal MVP first delivery with login, project list, and base contract detail page.",
            produced_by=bob["address"]["address"],
            source_session_id=contract["work_session_id"],
            source_message_id="recorded-delivery-v1",
            artifacts=[
                {"kind": "preview", "uri": "https://preview.example/vendor-portal/v1", "label": "Preview v1"},
                {"kind": "commit", "uri": "git://ai-link-net/commit/v1-base", "label": "Commit v1-base", "digest": "sha256:v1-base"},
            ],
            produced_at=1776841076.072167,
        ),
        "execution_costs": cost_payload(
            contract_id=contract["contract_id"],
            actor_address=bob["address"]["address"],
            phase="implementation",
            provider="codex",
            model="gpt-5-codex",
            input_tokens=1200,
            output_tokens=450,
            cost_usd=0.37,
            runtime_ms=182000,
            notes="Initial implementation delivery turn",
            recorded_at=1776841076.072167,
        ),
    },
)
capture("S2_DELIVER_V1", "Bob", "Bob submits delivery v1 based on S1; Arbiter reviews active->completing and signs S2.", contract, previous_hash, previous_hash)
print(f"S2_DELIVER_V1: status={contract['status']} source={short_hash(previous_hash)} snapshot={short_hash(contract['current_snapshot_hash'])}")

previous_hash = contract["current_snapshot_hash"]
contract = contract_action(
    actor="Alex",
    kind="contract_rework",
    contract_json=contract,
    reason="Please add trust evidence for review: snapshot chain, approvals, and Arbiter attestation.",
)
capture("S3_REWORK", "Alex", "Alex requests rework from S2; Arbiter reviews party_a authorization and signs S3.", contract, previous_hash, previous_hash)
print(f"S3_REWORK: status={contract['status']} source={short_hash(previous_hash)} snapshot={short_hash(contract['current_snapshot_hash'])}")

previous_hash = contract["current_snapshot_hash"]
contract = contract_action(
    actor="Bob",
    kind="contract_complete",
    contract_json=contract,
    reason="Delivery v2: trust review view, signed snapshot chain, and approval evidence are added.",
    extra_payload={
        "delivery": delivery_payload(
            contract_id=contract["contract_id"],
            version="v2.0.0",
            summary="Second delivery adds trust evidence, signed snapshot chain, approval review, and Arbiter attestation context.",
            produced_by=bob["address"]["address"],
            source_session_id=contract["work_session_id"],
            source_message_id="recorded-delivery-v2",
            artifacts=[
                {"kind": "preview", "uri": "https://preview.example/vendor-portal/v2", "label": "Preview v2"},
                {"kind": "commit", "uri": "git://ai-link-net/commit/v2-trust", "label": "Commit v2-trust", "digest": "sha256:v2-trust"},
            ],
            produced_at=1776841158.774354,
        ),
        "execution_costs": cost_payload(
            contract_id=contract["contract_id"],
            actor_address=bob["address"]["address"],
            phase="rework",
            provider="codex",
            model="gpt-5-codex",
            input_tokens=900,
            output_tokens=320,
            cost_usd=0.24,
            runtime_ms=133000,
            notes="Rework delivery with trust evidence",
            recorded_at=1776841158.774354,
        ),
    },
)
capture("S4_DELIVER_V2", "Bob", "Bob submits delivery v2 based on S3; Arbiter signs S4.", contract, previous_hash, previous_hash)
print(f"S4_DELIVER_V2: status={contract['status']} source={short_hash(previous_hash)} snapshot={short_hash(contract['current_snapshot_hash'])}")

previous_hash = contract["current_snapshot_hash"]
contract = contract_action(
    actor="Alex",
    kind="contract_accept",
    contract_json=contract,
    reason="Alex accepts v2 as the final outsourced delivery.",
)
capture("S5_ACCEPT_DELIVERY", "Alex", "Alex accepts S4 delivery; Arbiter reviews completing->settling and signs S5.", contract, previous_hash, previous_hash)
print(f"S5_ACCEPT_DELIVERY: status={contract['status']} source={short_hash(previous_hash)} snapshot={short_hash(contract['current_snapshot_hash'])}")

previous_hash = contract["current_snapshot_hash"]
contract = contract_action(
    actor="Alex",
    kind="contract_rate",
    contract_json=contract,
    rating=5,
    review="Clear delivery history, clean rework loop, and auditable trust evidence.",
)
capture("S6_RATE", "Alex", "Alex rates Bob after acceptance; Arbiter signs the final reputation input snapshot S6.", contract, previous_hash, previous_hash)
print(f"S6_RATE: status={contract['status']} source={short_hash(previous_hash)} snapshot={short_hash(contract['current_snapshot_hash'])}")

with open(CONTRACT_FILE, "w", encoding="utf-8") as f:
    json.dump(contract, f, indent=2, ensure_ascii=False)

web_url = (
    f"http://localhost:{os.environ['TRUST_DEMO_UI_PORT']}/?entity_uid={alex['entity_uid']}"
    f"&host_url=http%3A//127.0.0.1%3A{os.environ['TRUST_DEMO_PORT']}#/trade"
)
summary = {
    "scenario": "Alex creates task -> Bob accepts -> Arbiter reviews signed snapshots -> Bob delivers v1 -> Alex requests rework -> Bob delivers v2 -> Alex accepts and rates",
    "api_host": BASE.removesuffix("/api/v1"),
    "web_trade_url_for_alex": web_url,
    "contract_detail_api": f"{BASE}/trade/contracts/{contract['contract_id']}",
    "contract_id": contract["contract_id"],
    "participants": {
        "alex": {"uid": alex["entity_uid"], "address": alex["address"]["address"]},
        "bob": {"uid": bob["entity_uid"], "address": bob["address"]["address"]},
        "arbiter": {"uid": arbiter["entity_uid"], "address": arbiter["address"]["address"]},
    },
    "final": {
        "status": contract["status"],
        "rating": contract["rating"],
        "review": contract["review"],
        "rework_count": contract["rework_count"],
        "terms_hash": contract["terms_hash"],
        "snapshot_hash": contract["current_snapshot_hash"],
        "attestation_valid": validate_attestation(contract),
        "all_steps_attested": all(step["attestation_valid"] for step in timeline),
        "all_steps_linked": all(step["prev_links_to_previous_step"] for step in timeline),
    },
    "timeline": timeline,
}
with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

with open(TIMELINE_FILE, "w", encoding="utf-8") as f:
    f.write("# Alex/Bob Trade & Trust Delivery Timeline\n\n")
    f.write("| Step | Actor | Status | Source Snapshot | Snapshot | Prev Linked | Attested | Last Action |\n")
    f.write("|---|---|---|---|---|---|---|---|\n")
    for step in timeline:
        f.write(
            f"| {step['label']} | {step['actor']} | {step['status']} | "
            f"`{short_hash(step['source_snapshot_hash_used'])}` | "
            f"`{short_hash(step['snapshot_hash'])}` | "
            f"{step['prev_links_to_previous_step']} | "
            f"{step['attestation_valid']} | {step['last_action']} |\n"
        )
    f.write("\n## Notes\n\n")
    for step in timeline:
        f.write(f"- **{step['label']}**: {step['message']}\n")

print()
print("final proof:")
print(json.dumps(summary["final"], indent=2, ensure_ascii=False))
print()
print("snapshot timeline:")
for step in timeline:
    print(
        f"  {step['label']}: actor={step['actor']} status={step['status']} "
        f"source={short_hash(step['source_snapshot_hash_used'])} "
        f"snapshot={short_hash(step['snapshot_hash'])} "
        f"linked={step['prev_links_to_previous_step']} attested={step['attestation_valid']}"
    )
PY

echo
echo "========== Recording Complete =========="
echo "terminal_log: ${LOG_FILE}"
if [[ -f "${CAST_FILE}" ]]; then
  echo "terminal_cast: ${CAST_FILE}"
fi
echo "summary_json: ${SUMMARY_FILE}"
echo "timeline_md: ${TIMELINE_FILE}"
echo "contract_json: ${CONTRACT_FILE}"
echo
echo "If Web UI was started or is already running, open:"
echo "  $(python3 - <<PY
import json
with open("${SUMMARY_FILE}", encoding="utf-8") as f:
    print(json.load(f)["web_trade_url_for_alex"])
PY
)"
