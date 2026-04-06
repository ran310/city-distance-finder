#!/bin/bash
# CodeDeploy: venv, pip, merge Iceberg credentials into systemd env file.
set -euxo pipefail

APP_DIR="/opt/city-distance-finder/app"
VENV="/opt/city-distance-finder/venv"
ENV_FILE="/etc/city-distance-finder.env"
SECRET_SRC="${APP_DIR}/deploy/runtime-secrets.env"

if command -v python3.11 &>/dev/null; then
  PY=python3.11
elif command -v python3 &>/dev/null; then
  PY=python3
else
  echo "ERROR: python3 not found on the host." >&2
  exit 1
fi

if [[ ! -d "${VENV}" ]]; then
  "${PY}" -m venv "${VENV}"
fi

"${VENV}/bin/pip" install --upgrade pip
"${VENV}/bin/pip" install --no-cache-dir -r "${APP_DIR}/requirements.txt"

if [[ ! -f "${ENV_FILE}" ]]; then
  touch "${ENV_FILE}"
fi
chmod 600 "${ENV_FILE}"

sed -i '/^ICEBERG_USER=/d;/^ICEBERG_PASSWORD=/d;/^ICEBERG_BEARER_TOKEN=/d' "${ENV_FILE}" || true

if [[ -f "${SECRET_SRC}" ]]; then
  grep -E '^(ICEBERG_USER|ICEBERG_PASSWORD|ICEBERG_BEARER_TOKEN)=' "${SECRET_SRC}" >> "${ENV_FILE}" || true
  rm -f "${SECRET_SRC}"
fi

if ! grep -q '^APPLICATION_ROOT=' "${ENV_FILE}" 2>/dev/null; then
  echo 'APPLICATION_ROOT=/city-distance-finder' >> "${ENV_FILE}"
else
  sed -i 's|^APPLICATION_ROOT=.*|APPLICATION_ROOT=/city-distance-finder|' "${ENV_FILE}"
fi

chmod 600 "${ENV_FILE}"
echo "AfterInstall complete"
