#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$PROJECT_DIR/backend.pid"

if [ -f "$PIDFILE" ]; then
  pid=$(cat "$PIDFILE")
  if kill -0 "$pid" 2>/dev/null; then
    echo "Backend running (pid=$pid)"
    ss -ltnp | grep :8000 || true
    exit 0
  else
    echo "Stale pidfile (pid=$pid)"
  fi
fi

# Fallback: check for uvicorn process
pids=$(pgrep -f "uvicorn main:app" || true)
if [ -n "$pids" ]; then
  echo "uvicorn processes: $pids"
  ss -ltnp | grep :8000 || true
else
  echo "Backend not running"
fi
