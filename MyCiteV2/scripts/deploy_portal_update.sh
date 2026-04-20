#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: deploy_portal_update.sh [options]

Deploy live portal updates from this repo for one instance:
  - data updates: sync /srv/repo/mycite-core/deployed/<instance> into
    /srv/mycite-state/instances/<instance>
  - code updates: bump the portal build id and restart portal service

You can deploy either data, code, or both in one run.

Options:
  --instance <fnd|tff>     Instance to deploy. Default: fnd

  --data                   Sync deployed data into live instance state.
                           (copies deployed/<instance>/data -> live/data)
  --public                 Sync deployed public files into live state.
                           (copies deployed/<instance>/public -> live/public)
  --private                Sync deployed private files into live state.
                           (copies deployed/<instance>/private -> live/private)
  --tools-only             Sync only private/utilities/tools via existing helper.
                           Safe package-only mode unless --include-tool-state is also set.
  --tool <slug>            Tool slug to sync when --tools-only is used. Repeatable.
  --include-tool-state     With --tools-only, sync full tool tree including state.

  --code                   Deploy portal code changes (build bump + restart + health).
  --all                    Equivalent to: --data --public --private --code

  --build-label <label>    Build id label for code deploy. Default: manual-update
  --skip-build-bump        Do not write /srv/compose/portals/v2_portal_build.env
  --skip-restart           Do not restart portal service
  --skip-health            Do not hit /portal/healthz
  --skip-verify           Skip post-sync rsync verification checks.

  --dry-run                Show actions without changing files or services
  --help                   Show this help text

Examples:
  # Deploy only data snapshot updates for fnd
  deploy_portal_update.sh --instance fnd --data

  # Deploy only portal code updates for fnd
  deploy_portal_update.sh --instance fnd --code

  # Deploy data + code for tff
  deploy_portal_update.sh --instance tff --data --code

  # Sync only aws-csm tool package files for fnd (safe mode)
  deploy_portal_update.sh --instance fnd --tools-only --tool aws-csm
EOF
}

log() {
  printf '[deploy_portal_update] %s\n' "$*"
}

fail() {
  printf '[deploy_portal_update] ERROR: %s\n' "$*" >&2
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

run_or_echo() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

verify_sync() {
  local src="$1"
  local dst="$2"
  local label="$3"
  require_dir "$src"
  require_dir "$dst"
  log "Verifying ${label} sync parity"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] '
    printf '%q ' rsync -ani --delete "${src}/" "${dst}/"
    printf '\n'
    return 0
  fi
  local diff
  diff="$(rsync -ani --delete "${src}/" "${dst}/")"
  if [[ -n "$diff" ]]; then
    printf '%s\n' "$diff" >&2
    fail "Verification failed for ${label}; live tree differs from deployed source."
  fi
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

sync_tree() {
  local src="$1"
  local dst="$2"
  local label="$3"
  require_dir "$src"
  mkdir -p "$dst"
  log "Syncing ${label}: ${src} -> ${dst}"
  run_or_echo rsync -a --delete "${src}/" "${dst}/"
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

  log "Restart command failed or was blocked; signaling gunicorn MainPID to trigger Restart=on-failure"
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

run_health_check() {
  [[ -n "$PORT" ]] || fail "No health-check port is known for instance ${INSTANCE}"
  local url="http://127.0.0.1:${PORT}/portal/healthz"
  local attempts=20
  local sleep_seconds=1
  local attempt
  log "Checking health endpoint on port ${PORT} (up to ${attempts}s wait)"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] '
    printf '%q ' curl -fsS "$url"
    printf '\n'
    return 0
  fi
  for attempt in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null; then
      curl -fsS "$url"
      return 0
    fi
    sleep "$sleep_seconds"
  done
  fail "Health endpoint did not become ready at ${url} within ${attempts}s"
}

INSTANCE="fnd"
DO_DATA="0"
DO_PUBLIC="0"
DO_PRIVATE="0"
DO_TOOLS_ONLY="0"
DO_CODE="0"
BUILD_LABEL="manual-update"
SKIP_BUILD_BUMP="0"
SKIP_RESTART="0"
SKIP_HEALTH="0"
DRY_RUN="0"
INCLUDE_TOOL_STATE="0"
SKIP_VERIFY="0"
TOOLS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance)
      [[ $# -ge 2 ]] || fail "--instance requires a value"
      INSTANCE="$2"
      shift 2
      ;;
    --data)
      DO_DATA="1"
      shift
      ;;
    --public)
      DO_PUBLIC="1"
      shift
      ;;
    --private)
      DO_PRIVATE="1"
      shift
      ;;
    --tools-only)
      DO_TOOLS_ONLY="1"
      shift
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
    --code)
      DO_CODE="1"
      shift
      ;;
    --all)
      DO_DATA="1"
      DO_PUBLIC="1"
      DO_PRIVATE="1"
      DO_CODE="1"
      shift
      ;;
    --build-label)
      [[ $# -ge 2 ]] || fail "--build-label requires a value"
      BUILD_LABEL="$2"
      shift 2
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
    --skip-verify)
      SKIP_VERIFY="1"
      shift
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
SYNC_HELPER="${SCRIPT_DIR}/deploy_portal_sync.sh"

require_dir "$REPO_ROOT"
require_dir "$DEPLOYED_ROOT"
require_dir "$LIVE_ROOT"

if [[ "$DO_TOOLS_ONLY" == "1" ]] && [[ ${#TOOLS[@]} -eq 0 ]]; then
  fail "--tools-only requires at least one --tool <slug>"
fi

if [[ "$DO_DATA" == "0" && "$DO_PUBLIC" == "0" && "$DO_PRIVATE" == "0" && "$DO_TOOLS_ONLY" == "0" && "$DO_CODE" == "0" ]]; then
  fail "No actions selected. Use --data and/or --code (or --all)."
fi

if [[ "$DO_DATA" == "1" ]]; then
  sync_tree "${DEPLOYED_ROOT}/data" "${LIVE_ROOT}/data" "data snapshot"
  if [[ "$SKIP_VERIFY" != "1" ]]; then
    verify_sync "${DEPLOYED_ROOT}/data" "${LIVE_ROOT}/data" "data snapshot"
  fi
fi
if [[ "$DO_PUBLIC" == "1" ]]; then
  sync_tree "${DEPLOYED_ROOT}/public" "${LIVE_ROOT}/public" "public files"
  if [[ "$SKIP_VERIFY" != "1" ]]; then
    verify_sync "${DEPLOYED_ROOT}/public" "${LIVE_ROOT}/public" "public files"
  fi
fi
if [[ "$DO_PRIVATE" == "1" ]]; then
  sync_tree "${DEPLOYED_ROOT}/private" "${LIVE_ROOT}/private" "private files"
  if [[ "$SKIP_VERIFY" != "1" ]]; then
    verify_sync "${DEPLOYED_ROOT}/private" "${LIVE_ROOT}/private" "private files"
  fi
fi

if [[ "$DO_TOOLS_ONLY" == "1" ]]; then
  require_dir "$SCRIPT_DIR"
  require_dir "$(dirname "$SYNC_HELPER")"
  [[ -f "$SYNC_HELPER" ]] || fail "Missing helper script: ${SYNC_HELPER}"
  for tool_slug in "${TOOLS[@]}"; do
    cmd=("$SYNC_HELPER" "--instance" "$INSTANCE" "--tool" "$tool_slug" "--skip-build-bump" "--skip-restart" "--skip-health")
    if [[ "$INCLUDE_TOOL_STATE" == "1" ]]; then
      cmd+=("--include-tool-state")
    fi
    if [[ "$DRY_RUN" == "1" ]]; then
      cmd+=("--dry-run")
    fi
    log "Delegating tool sync for ${tool_slug} to deploy_portal_sync.sh"
    run_or_echo "${cmd[@]}"
  done
fi

if [[ "$DO_CODE" == "1" ]]; then
  if [[ "$SKIP_BUILD_BUMP" != "1" ]]; then
    write_build_id "$BUILD_LABEL"
  fi
  if [[ "$SKIP_RESTART" != "1" ]]; then
    restart_service
  fi
  if [[ "$SKIP_HEALTH" != "1" ]]; then
    run_health_check
  fi
fi

log "Completed for instance ${INSTANCE}"
