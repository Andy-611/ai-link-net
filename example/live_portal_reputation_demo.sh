#!/usr/bin/env bash
# Start a live reputation demo that ends with a signed, rated vendor contract so
# the Reputation page can display derived vendor reputation.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${TRUST_DEMO_PORT:-18190}"
UI_PORT="${TRUST_DEMO_UI_PORT:-5208}"
FP_HOME_DIR="${TRUST_DEMO_FP_HOME:-/tmp/aln-reputation-dashboard-live}"
OUT_DIR="${TRUST_DEMO_OUT_DIR:-${ROOT_DIR}/demo/recordings/reputation-dashboard-live}"
SUMMARY_FILE="${OUT_DIR}/summary.json"

mkdir -p "${OUT_DIR}"

cd "${ROOT_DIR}"

TRUST_DEMO_NO_ASCIINEMA=1 \
START_TRUST_DEMO_UI=1 \
KEEP_TRUST_DEMO_HOST=1 \
TRUST_DEMO_PORT="${PORT}" \
TRUST_DEMO_UI_PORT="${UI_PORT}" \
TRUST_DEMO_FP_HOME="${FP_HOME_DIR}" \
TRUST_DEMO_OUT_DIR="${OUT_DIR}" \
bash demo/record_alex_bob_delivery_demo.sh

if [[ ! -f "${SUMMARY_FILE}" ]]; then
  echo "Missing summary file: ${SUMMARY_FILE}"
  exit 1
fi

python3 - <<PY
import json
from pathlib import Path
from urllib.parse import quote

summary = json.loads(Path("${SUMMARY_FILE}").read_text(encoding="utf-8"))
api_host = summary["api_host"]
alex_uid = summary["participants"]["alex"]["uid"]

trade_url = f"http://127.0.0.1:${UI_PORT}/?entity_uid={alex_uid}&host_url={quote(api_host, safe='')}#/trade"
reputation_url = f"http://127.0.0.1:${UI_PORT}/?entity_uid={alex_uid}&host_url={quote(api_host, safe='')}#/reputation"

print()
print("========== Reputation Demo Ready ==========")
print(f"api_host: {api_host}")
print(f"trade_url: {trade_url}")
print(f"reputation_url: {reputation_url}")
print(f"summary_json: ${SUMMARY_FILE}")
print(f"contract_json: ${OUT_DIR}/contract.json")
print()
print("Recommended acceptance path:")
print("1. Open reputation_url")
print("2. Inspect vendor reputation score, confidence, and contract contributions")
print("3. Open trade_url to inspect trust evidence and delivery/cost artifacts")
PY
