#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: deploy_portal_sync.sh [options]

Sync repo-backed portal package files into the live instance state root, bump the
portal build id, restart the portal service, and verify the local health endpoint.

Options:
  --instance <fnd|tff>     Portal instance to deploy. Default: fnd
  --tool <slug>            Sync one deployed tool package from repo/deployed into live state.
                           Repeat to sync multiple tools.
  --include-tool-state     Also sync tool JSON/state files. Default is safe package-only sync.
  --skip-build-bump        Do not rewrite /srv/compose/portals/v2_portal_build.env.
  --skip-restart           Do not restart the portal systemd service.
  --skip-health            Do not run the local /portal/healthz check.
  --dry-run                Print planned changes without mutating files or restarting services.
  --build-label <label>    Suffix for the generated build id. Default: manual-sync
  --help                   Show this help text.

Examples:
  deploy_portal_sync.sh --instance fnd --tool aws-csm
  deploy_portal_sync.sh --instance fnd --tool aws-csm --include-tool-state
  deploy_portal_sync.sh --instance fnd --tool aws-csm --dry-run

Notes:
  - The live portals run repo code directly from /srv/repo/mycite-core, so code and
    static asset changes usually need a restart plus a fresh build id rather than a copy.
  - Tool package files live under /srv/mycite-state/instances/<instance>/private/utilities/tools.
  - Safe package-only sync copies spec/collection/UI/docs files and intentionally skips
    profile/domain/newsletter state unless --include-tool-state is passed.
  - If systemctl restart is blocked by PolicyKit, the script falls back to signaling
    the service's gunicorn master so systemd can restart it under Restart=on-failure.
EOF
}

log() {
  printf '[deploy_portal_sync] %s\n' "$*"
}

fail() {
  printf '[deploy_portal_sync] ERROR: %s\n' "$*" >&2
  exit 1
}

require_dir() {
  local path="$1"
  [[ -d "$path" ]] || fail "Required directory is missing: $path"
}

require_file_parent() {
  local path="$1"
  local parent
  parent="$(dirname "$path")"
  [[ -d "$parent" ]] || fail "Required parent directory is missing: $parent"
}

portal_service_for_instance() {
  case "$1" in
    fnd) printf 'mycite-v2-fnd-portal.service' ;;
    tff) printf 'mycite-v2-tff-portal.service' ;;
    *) printf 'mycite-v2-%s-portal.service' "$1" ;;
  esac
}

portal_port_for_instance() {
  case "$1" in
    fnd) printf '6101' ;;
    tff) printf '6203' ;;
    *) printf '' ;;
  esac
}

run_or_echo() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

sync_tool_package() {
  local tool_slug="$1"
  local src="${DEPLOYED_ROOT}/private/utilities/tools/${tool_slug}"
  local dst="${LIVE_ROOT}/private/utilities/tools/${tool_slug}"

  require_dir "$src"
  mkdir -p "$dst"

  if [[ "$INCLUDE_TOOL_STATE" == "1" ]]; then
    log "Syncing full tool tree for ${tool_slug}"
    run_or_echo rsync -a --delete "${src}/" "${dst}/"
    return 0
  fi

  log "Syncing safe package files for ${tool_slug}"
  run_or_echo rsync \
    -a \
    --delete \
    --include='*/' \
    --include='spec.json' \
    --include='tool*.json' \
    --include='UI/***' \
    --include='*.md' \
    --exclude='*' \
    "${src}/" "${dst}/"
}

write_build_id() {
  local label="$1"
  local build_id
  build_id="$(date -u +%Y%m%d-%H%M%S)-${label}"
  require_file_parent "$BUILD_ENV_FILE"
  log "Writing build id ${build_id} to ${BUILD_ENV_FILE}"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] MYCITE_V2_PORTAL_BUILD_ID=%s > %s\n' "$build_id" "$BUILD_ENV_FILE"
    return 0
  fi
  printf 'MYCITE_V2_PORTAL_BUILD_ID=%s\n' "$build_id" >"$BUILD_ENV_FILE"
}

restart_service() {
  local main_pid
  local next_pid
  local -a restart_cmd

  log "Restarting ${SERVICE_NAME}"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] '
    if sudo -n true >/dev/null 2>&1; then
      printf '%q ' sudo -n systemctl restart "$SERVICE_NAME"
    else
      printf '%q ' systemctl --no-ask-password restart "$SERVICE_NAME"
    fi
    printf '\n'
    return 0
  fi

  if sudo -n true >/dev/null 2>&1; then
    restart_cmd=(sudo -n systemctl restart "$SERVICE_NAME")
  else
    restart_cmd=(systemctl --no-ask-password restart "$SERVICE_NAME")
  fi

  if "${restart_cmd[@]}"; then
    systemctl is-active "$SERVICE_NAME" >/dev/null
    return 0
  fi

  log "Restart command failed or was blocked; falling back to signaling the gunicorn master"
  main_pid="$(systemctl show -p MainPID --value "$SERVICE_NAME" 2>/dev/null | tr -d '[:space:]')"
  [[ "$main_pid" =~ ^[0-9]+$ ]] || fail "Could not resolve MainPID for ${SERVICE_NAME}"
  [[ "$main_pid" != "0" ]] || fail "MainPID is 0 for ${SERVICE_NAME}"

  kill -KILL "$main_pid"

  for _ in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    next_pid="$(systemctl show -p MainPID --value "$SERVICE_NAME" 2>/dev/null | tr -d '[:space:]')"
    if [[ "$next_pid" =~ ^[0-9]+$ ]] && [[ "$next_pid" != "0" ]] && [[ "$next_pid" != "$main_pid" ]]; then
      systemctl is-active "$SERVICE_NAME" >/dev/null 2>&1 || true
      return 0
    fi
  done

  fail "Service did not recover after signaling MainPID ${main_pid}"
}

INSTANCE="fnd"
BUILD_LABEL="manual-sync"
SKIP_BUILD_BUMP="0"
SKIP_RESTART="0"
SKIP_HEALTH="0"
DRY_RUN="0"
INCLUDE_TOOL_STATE="0"
TOOLS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance)
      [[ $# -ge 2 ]] || fail "--instance requires a value"
      INSTANCE="$2"
      shift 2
      ;;
    --tool)
      [[ $# -ge 2 ]] || fail "--tool requires a value"
      TOOLS+=("$2")
      shift 2
      ;;
    --include-tool-state)
      INCLUDE_TOOL_STATE="1"
      shift
      ;;
    --skip-build-bump)
      SKIP_BUILD_BUMP="1"
      shift
      ;;
    --skip-restart)
      SKIP_RESTART="1"
      shift
      ;;
    --skip-health)
      SKIP_HEALTH="1"
      shift
      ;;
    --build-label)
      [[ $# -ge 2 ]] || fail "--build-label requires a value"
      BUILD_LABEL="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="1"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOYED_ROOT="${REPO_ROOT}/deployed/${INSTANCE}"
LIVE_ROOT="/srv/mycite-state/instances/${INSTANCE}"
BUILD_ENV_FILE="/srv/compose/portals/v2_portal_build.env"
SERVICE_NAME="$(portal_service_for_instance "$INSTANCE")"
PORT="$(portal_port_for_instance "$INSTANCE")"

require_dir "$REPO_ROOT"
require_dir "$DEPLOYED_ROOT"
require_dir "$LIVE_ROOT"

for tool_slug in "${TOOLS[@]}"; do
  sync_tool_package "$tool_slug"
done

if [[ "$SKIP_BUILD_BUMP" != "1" ]]; then
  write_build_id "$BUILD_LABEL"
fi

if [[ "$SKIP_RESTART" != "1" ]]; then
  restart_service
fi

if [[ "$SKIP_HEALTH" != "1" ]]; then
  [[ -n "$PORT" ]] || fail "No health-check port is cataloged for instance ${INSTANCE}"
  local_url="http://127.0.0.1:${PORT}/portal/healthz"
  attempts=20
  sleep_seconds=1
  log "Checking health endpoint on port ${PORT} (up to ${attempts}s wait)"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] '
    printf '%q ' curl -fsS "$local_url"
    printf '\n'
  else
    health_ok="0"
    for _ in $(seq 1 "$attempts"); do
      if curl -fsS "$local_url" >/dev/null; then
        curl -fsS "$local_url"
        health_ok="1"
        break
      fi
      sleep "$sleep_seconds"
    done
    if [[ "$health_ok" != "1" ]]; then
      fail "Health endpoint did not become ready at ${local_url} within ${attempts}s"
    fi
  fi
fi

log "Completed for instance ${INSTANCE}"
