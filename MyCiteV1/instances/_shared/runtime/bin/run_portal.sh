#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

export MYCITE_REPO_ROOT="${MYCITE_REPO_ROOT:-${REPO_ROOT}}"
export MYCITE_PORTALS_ROOT="${MYCITE_PORTALS_ROOT:-${REPO_ROOT}/instances}"
export PORTAL_RUNTIME_FLAVOR="${PORTAL_RUNTIME_FLAVOR:-fnd}"
export PORTAL_INSTANCE_ID="${PORTAL_INSTANCE_ID:-${PORTAL_RUNTIME_FLAVOR}}"
export MYCITE_INSTANCE_STATE_ROOT="${MYCITE_INSTANCE_STATE_ROOT:-/srv/mycite-state/instances/${PORTAL_INSTANCE_ID}}"
export PRIVATE_DIR="${PRIVATE_DIR:-${MYCITE_INSTANCE_STATE_ROOT}/private}"
export PUBLIC_DIR="${PUBLIC_DIR:-${MYCITE_INSTANCE_STATE_ROOT}/public}"
export DATA_DIR="${DATA_DIR:-${MYCITE_INSTANCE_STATE_ROOT}/data}"

if [[ -n "${MYCITE_PORTAL_VENV:-}" && -x "${MYCITE_PORTAL_VENV}/bin/gunicorn" ]]; then
  GUNICORN_BIN="${MYCITE_PORTAL_VENV}/bin/gunicorn"
else
  GUNICORN_BIN="$(command -v gunicorn)"
fi

if [[ -z "${GUNICORN_BIN:-}" || ! -x "${GUNICORN_BIN}" ]]; then
  echo "gunicorn executable not found" >&2
  exit 1
fi

PORTAL_BIND_PORT="${PORTAL_BIND_PORT:-5101}"
PORTAL_GUNICORN_WORKERS="${PORTAL_GUNICORN_WORKERS:-2}"
PORTAL_GUNICORN_THREADS="${PORTAL_GUNICORN_THREADS:-4}"
PORTAL_GUNICORN_TIMEOUT="${PORTAL_GUNICORN_TIMEOUT:-60}"

cd "${RUNTIME_DIR}"

exec "${GUNICORN_BIN}" \
  --workers "${PORTAL_GUNICORN_WORKERS}" \
  --threads "${PORTAL_GUNICORN_THREADS}" \
  --timeout "${PORTAL_GUNICORN_TIMEOUT}" \
  --worker-tmp-dir /dev/shm \
  --bind "127.0.0.1:${PORTAL_BIND_PORT}" \
  --access-logfile - \
  --error-logfile - \
  "$@" \
  app:app
