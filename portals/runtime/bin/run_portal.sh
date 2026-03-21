#!/usr/bin/env bash
set -euo pipefail

: "${PORTAL_BIND_PORT:?PORTAL_BIND_PORT is required}"

PORTAL_WORKERS="${PORTAL_WORKERS:-2}"
PORTAL_THREADS="${PORTAL_THREADS:-4}"
PORTAL_TIMEOUT="${PORTAL_TIMEOUT:-60}"
MYCITE_PORTALS_ROOT="${MYCITE_PORTALS_ROOT:-/srv/repo/mycite-core/portals}"
MYCITE_PORTAL_RUNTIME_DIR="${MYCITE_PORTAL_RUNTIME_DIR:-${MYCITE_PORTALS_ROOT}/runtime}"
MYCITE_PORTAL_VENV="${MYCITE_PORTAL_VENV:-/srv/repo/mycite-core/.venv}"
GUNICORN_BIN="${MYCITE_PORTAL_GUNICORN_BIN:-${MYCITE_PORTAL_VENV}/bin/gunicorn}"

if [[ ! -x "${GUNICORN_BIN}" ]]; then
  echo "gunicorn executable not found: ${GUNICORN_BIN}" >&2
  exit 1
fi

cd "${MYCITE_PORTAL_RUNTIME_DIR}"

exec "${GUNICORN_BIN}" \
  --workers "${PORTAL_WORKERS}" \
  --threads "${PORTAL_THREADS}" \
  --timeout "${PORTAL_TIMEOUT}" \
  --worker-tmp-dir /dev/shm \
  --bind "127.0.0.1:${PORTAL_BIND_PORT}" \
  --access-logfile - \
  --error-logfile - \
  app:app
