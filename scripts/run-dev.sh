#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
BACKEND_DIR="$ROOT_DIR/src/bpmn_assistant"
LAYOUT_DIR="$ROOT_DIR/src/bpmn_layout_server"
FRONTEND_DIR="$ROOT_DIR/src/bpmn_frontend"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
LAYOUT_HOST="${LAYOUT_HOST:-127.0.0.1}"
LAYOUT_PORT="${LAYOUT_PORT:-3001}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

command -v uv >/dev/null || {
  echo "error: uv is required but was not found in PATH" >&2
  exit 1
}
command -v npm >/dev/null || {
  echo "error: npm is required but was not found in PATH" >&2
  exit 1
}
command -v node >/dev/null || {
  echo "error: node is required but was not found in PATH" >&2
  exit 1
}

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  echo "error: $BACKEND_DIR/.env is missing. Copy .env.example and add your API keys first." >&2
  exit 1
fi

ensure_node_modules() {
  local dir="$1"
  if [[ ! -d "$dir/node_modules" ]]; then
    echo "Installing npm dependencies in $dir"
    (cd "$dir" && npm install)
  fi
}

ensure_node_modules "$LAYOUT_DIR"
ensure_node_modules "$FRONTEND_DIR"

cleanup() {
  if [[ "${PIDS[*]-}" != "" ]]; then
    echo
    echo "Stopping services..."
    for pid in "${PIDS[@]}"; do
      kill "$pid" 2>/dev/null || true
    done
  fi
}

trap cleanup INT TERM EXIT

start_backend() {
  echo "Starting FastAPI backend on http://$API_HOST:$API_PORT"
  cd "$BACKEND_DIR"
  uv run uvicorn app:app --host "$API_HOST" --port "$API_PORT"
}

start_layout() {
  echo "Starting layout server on http://$LAYOUT_HOST:$LAYOUT_PORT"
  cd "$LAYOUT_DIR"
  PORT="$LAYOUT_PORT" HOST="$LAYOUT_HOST" node server.js
}

start_frontend() {
  echo "Starting frontend on http://$FRONTEND_HOST:$FRONTEND_PORT"
  cd "$FRONTEND_DIR"
  VITE_API_BASE_URL="http://$API_HOST:$API_PORT" \
  VITE_LAYOUT_BASE_URL="http://$LAYOUT_HOST:$LAYOUT_PORT" \
  npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
}

PIDS=()
start_backend &
PIDS+=($!)
start_layout &
PIDS+=($!)
start_frontend &
PIDS+=($!)

echo "All services are running. Press Ctrl+C to stop."

wait
