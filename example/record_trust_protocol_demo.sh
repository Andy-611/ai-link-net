#!/usr/bin/env bash
# Record a reproducible Trade & Trust protocol demo.
#
# Output:
#   demo/recordings/trust-demo-<timestamp>/
#     terminal.cast     Asciinema terminal recording, when asciinema is installed
#     terminal.log      Full terminal transcript
#     summary.json      Human-readable proof summary
#     contract.json     Final contract JSON from the Trade API

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${TRUST_DEMO_PORT:-18150}"
HOST_NAME="${TRUST_DEMO_HOST:-trust-record-demo}"
FP_HOME_DIR="${TRUST_DEMO_FP_HOME:-/tmp/aln-trust-record-demo}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${TRUST_DEMO_OUT_DIR:-${ROOT_DIR}/demo/recordings/trust-demo-${STAMP}}"
CAST_FILE="${OUT_DIR}/terminal.cast"
LOG_FILE="${OUT_DIR}/terminal.log"
SUMMARY_FILE="${OUT_DIR}/summary.json"
CONTRACT_FILE="${OUT_DIR}/contract.json"

mkdir -p "${OUT_DIR}"

if [[ "${TRUST_DEMO_NO_ASCIINEMA:-0}" != "1" && -z "${ASCIINEMA_SESSION:-}" ]] && command -v asciinema >/dev/null 2>&1; then
  echo "Recording terminal demo with asciinema..."
  echo "output: ${CAST_FILE}"
  TRUST_DEMO_NO_ASCIINEMA=1 \
  TRUST_DEMO_OUT_DIR="${OUT_DIR}" \
  asciinema record \
    --overwrite \
    --idle-time-limit 1 \
    --title "Trade & Trust Protocol Demo" \
    --command "bash ${BASH_SOURCE[0]}" \
    "${CAST_FILE}"
  echo
  echo "Asciinema recording saved: ${CAST_FILE}"
  echo "Recording artifacts:"
  echo "  ${LOG_FILE}"
  echo "  ${SUMMARY_FILE}"
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

echo "========== Trade & Trust Protocol Demo Recording =========="
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

echo "1. Prepare isolated host config"
FP_HOME="${FP_HOME_DIR}" "${ALN}" host stop --host "${HOST_NAME}" >/dev/null 2>&1 || true
FP_HOME="${FP_HOME_DIR}" UV_CACHE_DIR=/tmp/uv-cache "${ALN}" host new \
  --name "${HOST_NAME}" \
  --bind-host 127.0.0.1 \
  --port "${PORT}" \
 

echo
echo "2. Wait for host health"
"${PYTHON}" - <<PY
import json
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
  echo "3. Start Web UI"
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm not found; skipping Web UI startup"
  elif [[ ! -d "${ROOT_DIR}/aln/web/node_modules" ]]; then
    echo "aln/web/node_modules not found; run npm install in aln/web first"
  else
    (
      cd "${ROOT_DIR}/aln/web"
      npm run dev -- --host 127.0.0.1 --port "${TRUST_DEMO_UI_PORT:-5173}"
    ) >/dev/null 2>&1 &
    UI_PID=$!
    echo "web_ui_pid: ${UI_PID}"
    echo "web_ui_base: http://localhost:${TRUST_DEMO_UI_PORT:-5173}"
  fi
  echo
fi

echo "3. Run Web API trust flow"
TRUST_DEMO_PORT="${PORT}" \
TRUST_DEMO_UI_PORT="${TRUST_DEMO_UI_PORT:-5173}" \
TRUST_SUMMARY_FILE="${SUMMARY_FILE}" \
TRUST_CONTRACT_FILE="${CONTRACT_FILE}" \
"${PYTHON}" - <<'PY'
import json
import os
import urllib.error
import urllib.request

BASE = f"http://127.0.0.1:{os.environ['TRUST_DEMO_PORT']}/api/v1"
SUMMARY_FILE = os.environ["TRUST_SUMMARY_FILE"]
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


arbiter = register("arbiter", "Arbiter", "Trust demo arbiter")
alice = register("human", "Alice", "Trust demo payer")
bob = register("human", "Bob", "Trust demo provider")

print("registered:")
print(f"  arbiter={arbiter['address']['address']}")
print(f"  alice={alice['address']['address']}")
print(f"  bob={bob['address']['address']}")

create = request("POST", "/trade/send", {
    "from_entity": "Alice",
    "kind": "contract_create",
    "payload": {
        "party_a": {"address": alice["address"]["address"]},
        "party_b": {"address": bob["address"]["address"]},
        "party_a_card": alice,
        "party_b_card": bob,
        "title": "Recorded Trust Demo Contract",
        "description": "Recorded through the Web Trade HTTP API; approved with revision, terms_hash, and source_snapshot_hash.",
        "amount": 42,
        "funding_mode": "direct",
    },
})

contract = latest_created_contract(
    create,
    title="Recorded Trust Demo Contract",
    party_a_address=alice["address"]["address"],
    party_b_address=bob["address"]["address"],
)
created_hash = contract["current_snapshot_hash"]
created_terms_hash = contract["terms_hash"]

print("created:")
print(f"  contract_id={contract['contract_id']}")
print(f"  status={contract['status']}")
print(f"  terms_hash={created_terms_hash}")
print(f"  snapshot_hash={created_hash}")
print(f"  approvals={[a['party_role'] for a in contract.get('approvals', [])]}")

request("POST", "/trade/send", {
    "from_entity": "Bob",
    "kind": "contract_approve",
    "payload": {
        "contract_id": contract["contract_id"],
        "expected_status": contract["status"],
        "revision": contract["draft_version"],
        "terms_hash": created_terms_hash,
        "source_snapshot_hash": created_hash,
    },
})

final_contract = request("GET", f"/trade/contracts/{contract['contract_id']}")["data"]

with open(CONTRACT_FILE, "w", encoding="utf-8") as f:
    json.dump(final_contract, f, indent=2, ensure_ascii=False)

summary = {
    "api_host": BASE.removesuffix("/api/v1"),
    "web_trade_url_for_alice": (
        f"http://localhost:{os.environ['TRUST_DEMO_UI_PORT']}/?entity_uid={alice['entity_uid']}"
        f"&host_url=http%3A//127.0.0.1%3A{os.environ['TRUST_DEMO_PORT']}#/trade"
    ),
    "contract_detail_api": f"{BASE}/trade/contracts/{contract['contract_id']}",
    "entities": {
        "arbiter": {"uid": arbiter["entity_uid"], "address": arbiter["address"]["address"]},
        "alice": {"uid": alice["entity_uid"], "address": alice["address"]["address"]},
        "bob": {"uid": bob["entity_uid"], "address": bob["address"]["address"]},
    },
    "contract_id": final_contract["contract_id"],
    "create": {
        "status": contract["status"],
        "terms_hash": created_terms_hash,
        "snapshot_hash": created_hash,
        "arbiter_attestation_present": bool(contract.get("attestation")),
        "approvals": [
            [a["party_role"], a["approved_revision"]]
            for a in contract.get("approvals", [])
        ],
    },
    "approve": {
        "status": final_contract["status"],
        "snapshot_hash_changed": final_contract["current_snapshot_hash"] != created_hash,
        "prev_snapshot_hash_linked": final_contract["attestation"]["prev_snapshot_hash"] == created_hash,
        "attestation_snapshot_hash_matches": (
            final_contract["attestation"]["snapshot_hash"]
            == final_contract["current_snapshot_hash"]
        ),
        "participant_snapshot_roles": [
            p["role"] for p in final_contract.get("participant_snapshots", [])
        ],
        "approvals": [
            [
                a["party_role"],
                a["approved_revision"],
                a["approved_terms_hash"] == final_contract["terms_hash"],
            ]
            for a in final_contract.get("approvals", [])
        ],
    },
}

with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print("approved:")
print(f"  status={summary['approve']['status']}")
print(f"  snapshot_hash_changed={summary['approve']['snapshot_hash_changed']}")
print(f"  prev_snapshot_hash_linked={summary['approve']['prev_snapshot_hash_linked']}")
print(f"  attestation_snapshot_hash_matches={summary['approve']['attestation_snapshot_hash_matches']}")
print(f"  approvals={summary['approve']['approvals']}")
print()
print(json.dumps(summary, indent=2, ensure_ascii=False))
PY

echo
echo "4. Verify Arbiter attestation cryptographically"
TRUST_CONTRACT_FILE="${CONTRACT_FILE}" \
"${PYTHON}" - <<'PY'
import json
import os

from fp.trade.hashing import verify_attestation
from fp.trade.models import Contract

with open(os.environ["TRUST_CONTRACT_FILE"], encoding="utf-8") as f:
    contract = Contract.model_validate(json.load(f))

arbiter = next(p for p in contract.participant_snapshots if p.role == "arbiter")
result = {
    "contract_id": contract.contract_id,
    "status": contract.status.value,
    "attestation_valid": verify_attestation(contract.to_snapshot(), arbiter.sign_public_key),
    "approval_roles": [a.party_role for a in contract.approvals],
    "same_terms_approved": [a.approved_terms_hash == contract.terms_hash for a in contract.approvals],
}
print(json.dumps(result, indent=2, ensure_ascii=False))
PY

echo
echo "========== Recording Complete =========="
echo "terminal_log: ${LOG_FILE}"
if [[ -f "${CAST_FILE}" ]]; then
  echo "terminal_cast: ${CAST_FILE}"
fi
echo "summary_json: ${SUMMARY_FILE}"
echo "contract_json: ${CONTRACT_FILE}"
echo
echo "If Node/npm is available, open the Web page with:"
echo "  $(python3 - <<PY
import json
with open("${SUMMARY_FILE}", encoding="utf-8") as f:
    print(json.load(f)["web_trade_url_for_alice"])
PY
)"
