#!/usr/bin/env bash
# Stop the Flask app started by scripts/start.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT/.flask-app.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No PID file — nothing to stop ($PID_FILE)"
  exit 1
fi

pid="$(cat "$PID_FILE")"
if ! kill -0 "$pid" 2>/dev/null; then
  echo "Stale PID file (process $pid not running)"
  rm -f "$PID_FILE"
  exit 1
fi

kill "$pid"
for _ in {1..30}; do
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "Stopped $pid"
    exit 0
  fi
  sleep 0.2
done

echo "Process still running; sending SIGKILL to $pid"
kill -9 "$pid" 2>/dev/null || true
rm -f "$PID_FILE"
echo "Stopped $pid"
