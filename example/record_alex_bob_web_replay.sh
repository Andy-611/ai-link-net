#!/usr/bin/env bash
# Record an actual browser UI replay for the Alex/Bob Trade & Trust scenario.
#
# This script starts a local demo host and Vite Web UI, opens the real Trade
# page in Chrome through Playwright, drives the contract lifecycle through the
# same HTTP API used by the Web app, refreshes the UI after each signed snapshot,
# and saves a browser video.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
PORT="${TRUST_DEMO_PORT:-18164}"
UI_PORT="${TRUST_DEMO_UI_PORT:-5179}"
HOST_NAME="${TRUST_DEMO_HOST:-alex-bob-web-replay}"
FP_HOME_DIR="${TRUST_DEMO_FP_HOME:-/tmp/aln-alex-bob-web-replay-${STAMP}}"
OUT_DIR="${TRUST_DEMO_OUT_DIR:-${ROOT_DIR}/demo/recordings/alex-bob-web-replay-${STAMP}}"
VIDEO_FILE="${OUT_DIR}/web-replay.mp4"
SUMMARY_FILE="${OUT_DIR}/summary.json"
CONTRACT_FILE="${OUT_DIR}/contract.json"
TIMELINE_FILE="${OUT_DIR}/timeline.md"
LOG_FILE="${OUT_DIR}/web-replay.log"

mkdir -p "${OUT_DIR}"

exec > >(tee "${LOG_FILE}") 2>&1

cd "${ROOT_DIR}"

PYTHON="${ROOT_DIR}/.venv/bin/python"
ALN="${ROOT_DIR}/.venv/bin/aln"

if [[ ! -x "${PYTHON}" || ! -x "${ALN}" ]]; then
  echo "Missing .venv runtime. Run: UV_CACHE_DIR=/tmp/uv-cache uv sync --extra dev"
  exit 1
fi

if [[ ! -d "${ROOT_DIR}/aln/web/node_modules/playwright" ]]; then
  echo "Missing Playwright. Run: cd aln/web && npm install --no-save playwright"
  exit 1
fi

if [[ ! -d "${ROOT_DIR}/aln/web/node_modules" ]]; then
  echo "Missing Web dependencies. Run: cd aln/web && npm install"
  exit 1
fi

cleanup() {
  if [[ "${KEEP_TRUST_DEMO_HOST:-0}" == "1" ]]; then
    echo "KEEP_TRUST_DEMO_HOST=1, leaving demo services running."
    return
  fi
  echo "Stopping demo services..."
  if [[ -n "${UI_PID:-}" ]] && kill -0 "${UI_PID}" >/dev/null 2>&1; then
    kill "${UI_PID}" >/dev/null 2>&1 || true
    wait "${UI_PID}" >/dev/null 2>&1 || true
  fi
  FP_HOME="${FP_HOME_DIR}" "${ALN}" host stop --host "${HOST_NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "========== Alex/Bob Web UI Replay Recording =========="
echo "host: ${HOST_NAME} http://127.0.0.1:${PORT}"
echo "web:  http://127.0.0.1:${UI_PORT}"
echo "out:  ${OUT_DIR}"
echo

FP_HOME="${FP_HOME_DIR}" "${ALN}" host stop --host "${HOST_NAME}" >/dev/null 2>&1 || true
FP_HOME="${FP_HOME_DIR}" UV_CACHE_DIR=/tmp/uv-cache "${ALN}" host new \
  --name "${HOST_NAME}" \
  --bind-host 127.0.0.1 \
  --port "${PORT}" \
 

"${PYTHON}" - <<PY
import time
import urllib.request

url = "http://127.0.0.1:${PORT}/health"
last_error = None
for _ in range(60):
    try:
        with urllib.request.urlopen(url, timeout=1) as resp:
            print("host health:", resp.read().decode("utf-8"))
            raise SystemExit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(0.25)
raise SystemExit(f"Host did not become healthy: {last_error}")
PY

(
  cd "${ROOT_DIR}/aln/web"
  npm run dev -- --host 127.0.0.1 --port "${UI_PORT}"
) >/dev/null 2>&1 &
UI_PID=$!
echo "web_ui_pid: ${UI_PID}"

"${PYTHON}" - <<PY
import time
import urllib.request

url = "http://127.0.0.1:${UI_PORT}/"
last_error = None
for _ in range(80):
    try:
        with urllib.request.urlopen(url, timeout=1) as resp:
            print("web health:", resp.status)
            raise SystemExit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(0.25)
raise SystemExit(f"Web UI did not become healthy: {last_error}")
PY

TRUST_DEMO_PORT="${PORT}" \
TRUST_DEMO_UI_PORT="${UI_PORT}" \
TRUST_VIDEO_FILE="${VIDEO_FILE}" \
TRUST_SUMMARY_FILE="${SUMMARY_FILE}" \
TRUST_CONTRACT_FILE="${CONTRACT_FILE}" \
TRUST_TIMELINE_FILE="${TIMELINE_FILE}" \
node "${ROOT_DIR}/demo/web_replay_alex_bob.mjs"

WEBM_FILE="$(find "${OUT_DIR}" -maxdepth 1 -name '*.webm' -print -quit)"
if [[ -n "${WEBM_FILE}" && -x "$(command -v ffmpeg)" ]]; then
  echo "Converting WebM to MP4..."
  ffmpeg -y \
    -i "${WEBM_FILE}" \
    -movflags faststart \
    -pix_fmt yuv420p \
    "${VIDEO_FILE}" >/dev/null 2>&1
elif [[ -n "${WEBM_FILE}" ]]; then
  echo "ffmpeg not found; leaving Playwright WebM video at: ${WEBM_FILE}"
fi

echo
echo "========== Web Replay Complete =========="
if [[ -f "${VIDEO_FILE}" ]]; then
  echo "video: ${VIDEO_FILE}"
elif [[ -n "${WEBM_FILE}" ]]; then
  echo "video: ${WEBM_FILE}"
fi
echo "summary: ${SUMMARY_FILE}"
echo "timeline: ${TIMELINE_FILE}"
echo "contract: ${CONTRACT_FILE}"
