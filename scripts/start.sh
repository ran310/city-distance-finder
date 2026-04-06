#!/usr/bin/env bash
# Start the Flask app in the background (default http://127.0.0.1:8086).
# Optional: PORT=9000 ./scripts/start.sh   FLASK_DEBUG=1 ./scripts/start.sh
#
# AWS (Iceberg warehouse on S3 + S3_USE_AWS_CREDENTIAL_CHAIN in appconfig.py):
# After `aws login` / `aws sso login`, run this script from the SAME terminal so AWS_PROFILE
# (and HOME) match. Check first: aws sts get-caller-identity
# If you start the app from an IDE or launchd, set AWS_PROFILE (and region) in that environment.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PID_FILE="$ROOT/.flask-app.pid"
LOG_FILE="$ROOT/.flask-app.log"
PORT="${PORT:-8086}"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE")"
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "Already running (PID $old_pid) — http://127.0.0.1:$PORT"
    exit 1
  fi
  rm -f "$PID_FILE"
fi

export PORT
export FLASK_DEBUG="${FLASK_DEBUG:-0}"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi

nohup "$PY" "$ROOT/app.py" >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

echo "Started PID $(cat "$PID_FILE") — http://127.0.0.1:$PORT"
echo "Log: $LOG_FILE"
