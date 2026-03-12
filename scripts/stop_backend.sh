#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$PROJECT_DIR/backend.pid"

if [ -f "$PIDFILE" ]; then
  pid=$(cat "$PIDFILE")
  echo "Stopping backend (pid=$pid)"
  kill "$pid" || true
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    echo "Backend did not stop, forcing"
    kill -9 "$pid" || true
  fi
  rm -f "$PIDFILE"
  echo "Stopped"
else
  echo "No pidfile found. Attempting to pkill by name..."
  pkill -f "uvicorn main:app" || true
  echo "Done"
fi
