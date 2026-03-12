#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$PROJECT_DIR/logs/backend.log"
PIDFILE="$PROJECT_DIR/logs/backend.pid"

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"

# If already running, report and exit
if [ -f "$PIDFILE" ]; then
  pid=$(cat "$PIDFILE")
  if kill -0 "$pid" 2>/dev/null; then
    echo "Backend already running (pid=$pid)"
    exit 0
  else
    echo "Stale pidfile found, removing"
    rm -f "$PIDFILE"
  fi
fi

# Load .env if present (simple KEY=VALUE parser)
if [ -f "$PROJECT_DIR/.env" ]; then
  echo "Loading .env"
  set -a
  # shellcheck disable=SC1090
  . "$PROJECT_DIR/.env"
  set +a
fi

# Start backend from src directory
cd "$PROJECT_DIR/src"
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > "$LOG" 2>&1 &
echo $! > "$PIDFILE"
sleep 0.5
echo "Started backend (pid=$(cat $PIDFILE)), logs: $LOG"
