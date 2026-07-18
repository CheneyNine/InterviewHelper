#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env.omni ]]; then
  echo "Missing $ROOT_DIR/.env.omni" >&2
  exit 1
fi

set -a
source .env.omni
set +a

: "${OMNI_API_KEY:?OMNI_API_KEY is required}"
: "${OMNI_MODEL:?OMNI_MODEL is required}"
: "${OMNI_SSH_HOST:?OMNI_SSH_HOST is required}"

OMNI_API_STYLE="${OMNI_API_STYLE:-recording}"
OMNI_SSH_PORT="${OMNI_SSH_PORT:-50020}"
OMNI_REMOTE_API_HOST="${OMNI_REMOTE_API_HOST:-127.0.0.1}"
OMNI_REMOTE_API_PORT="${OMNI_REMOTE_API_PORT:-50021}"
OMNI_LOCAL_API_PORT="${OMNI_LOCAL_API_PORT:-50021}"

CONTROL_SOCKET="/tmp/interviewhelper-omni-ssh-$$"
PIDS=()

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  ssh -S "$CONTROL_SOCKET" -O exit -p "$OMNI_SSH_PORT" "$OMNI_SSH_HOST" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

SSH_ARGS=(
  -M -S "$CONTROL_SOCKET" -fN
  -o ExitOnForwardFailure=yes
  -o StrictHostKeyChecking=accept-new
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=3
  -L "${OMNI_LOCAL_API_PORT}:${OMNI_REMOTE_API_HOST}:${OMNI_REMOTE_API_PORT}"
  -p "$OMNI_SSH_PORT"
  "$OMNI_SSH_HOST"
)

if [[ -n "${OMNI_SSH_PASSWORD:-}" ]]; then
  if ! command -v expect >/dev/null 2>&1; then
    echo "OMNI_SSH_PASSWORD is configured, but the local 'expect' command is unavailable." >&2
    exit 1
  fi
  OMNI_SSH_PASSWORD="$OMNI_SSH_PASSWORD" \
    /usr/bin/expect -f "$ROOT_DIR/scripts/ssh-with-password.exp" -- "${SSH_ARGS[@]}"
else
  ssh "${SSH_ARGS[@]}"
fi

OMNI_BASE_URL="http://127.0.0.1:${OMNI_LOCAL_API_PORT}/v1"
if ! curl -fsS --max-time 15 \
  -H "Authorization: Bearer ${OMNI_API_KEY}" \
  "${OMNI_BASE_URL}/models" >/dev/null; then
  echo "SSH tunnel is open, but Omni HTTP API is unavailable at remote ${OMNI_REMOTE_API_HOST}:${OMNI_REMOTE_API_PORT}." >&2
  echo "Check the remote Docker mapping or change OMNI_REMOTE_API_PORT in .env.omni." >&2
  exit 1
fi

mkdir -p .run

(
  cd services/interviewer
  ../../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
) >.run/interviewer.log 2>&1 &
PIDS+=("$!")

(
  cd services/api
  INTERVIEWER_BASE_URL=http://127.0.0.1:8001 \
  VLM_BASE_URL="$OMNI_BASE_URL" \
  VLM_API_KEY="$OMNI_API_KEY" \
  VLM_API_STYLE="$OMNI_API_STYLE" \
  VLM_MODEL="$OMNI_MODEL" \
  ../../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
) >.run/core-api.log 2>&1 &
PIDS+=("$!")

CODEX_DEPS="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies"
if [[ -x "$CODEX_DEPS/node/bin/node" ]]; then
  export PATH="$CODEX_DEPS/node/bin:$PATH"
fi

(
  cd apps/desktop
  ./node_modules/.bin/vite
) >.run/desktop.log 2>&1 &
PIDS+=("$!")

echo "InterviewHelper: http://127.0.0.1:1420/"
echo "Core API:       http://127.0.0.1:8000/"
echo "Interviewer:    http://127.0.0.1:8001/ (question generation uses the project default provider)"
echo "Omni VLM:       ${OMNI_BASE_URL}"
echo "Logs:           $ROOT_DIR/.run/"
echo "Press Ctrl+C to stop all local services and close the SSH tunnel."

wait
