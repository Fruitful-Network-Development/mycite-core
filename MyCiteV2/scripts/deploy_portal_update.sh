#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: deploy_portal_update.sh [options]

Deploy live portal updates from this repo for one instance:
  - data updates: sync /srv/repo/mycite-core/deployed/<instance> into
    /srv/webapps/mycite/<instance>
  - code updates: bump the portal build id and restart portal service

You can deploy either data, code, or both in one run.

Options:
  --instance <fnd|tff>     Instance to deploy. Default: fnd

  --data                   Sync deployed data into live instance state.
                           (copies deployed/<instance>/data -> live/data)
  --public                 Sync deployed public files into live state.
                           (copies deployed/<instance>/public -> live/public)
  --private                DISASTER RESTORE ONLY — refused without
                           --force-restore-private. The live private store is
                           CANONICAL (aws-csm mailbox truth, contacts, PayPal);
                           deployed/ is a DR skeleton, so deployed->live clobbers
                           live. To snapshot for DR, rsync live -> deployed.
  --force-restore-private  Confirm the destructive deployed->live private restore.
  --tools-only             Sync only private/utilities/tools via existing helper.
                           Safe package-only mode unless --include-tool-state is also set.
  --tool <slug>            Tool slug to sync when --tools-only is used. Repeatable.
  --include-tool-state     With --tools-only, sync full tool tree including state.

  --code                   Deploy portal code changes (build bump + restart + health).
  --all                    Equivalent to: --data --public --code
                           (NOT --private — that is disaster-restore-only now)

  --build-label <label>    Build id label for code deploy. Default: manual-update
  --skip-build-bump        Do not write /srv/compose/portals/v2_portal_build.env
  --skip-restart           Do not restart portal service
  --skip-health            Do not hit /portal/healthz
  --skip-smoke             Do not run the post-deploy public-form smoke gate
                           (connect/newsletter/donate per grantee domain).
  --skip-verify           Skip post-sync rsync verification checks.
  --skip-cts-gis-compile-check
                           Skip the FND CTS-GIS compile+validate step that normally
                           runs before portal restart when CTS-GIS sources are present.

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
  local build_id sha
  # Embed the on-disk git short-sha so healthz code_coherence can compare the
  # running build to HEAD even for a deploy-stamped (non-"git-") build label.
  sha="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || true)"
  build_id="$(date -u +%Y%m%d-%H%M%S)-${label}${sha:+-git${sha}}"
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
  local shell_url="http://127.0.0.1:${PORT}/portal/api/v2/shell"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] '
    printf '%q ' curl -fsS "$url"
    printf '\n[dry-run] '
    printf '%q ' curl -fsS -X POST "$shell_url" -H 'Content-Type: application/json' -d '{}'
    printf '\n'
    return 0
  fi
  for attempt in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null; then
      curl -fsS "$url"
      # The healthz GET only proves the process is up. POST the actual shell so a
      # 500ing shell (e.g. a stale/broken worker) FAILS the deploy instead of
      # silently shipping a blank portal.
      local shell_code
      shell_code="$(curl -s -m 10 -o /dev/null -w '%{http_code}' \
        -X POST "$shell_url" -H 'Content-Type: application/json' -d '{}')"
      # 200 = healthy. 503 = a well-formed app reporting service state (e.g. SQL
      # authority not yet seeded) — NOT a code crash, so don't block the deploy.
      # 500/502/504/000/4xx = a broken or down shell → fail the deploy.
      case "$shell_code" in
        200) log "Shell endpoint POST returned 200" ;;
        503) log "WARNING: shell endpoint POST returned 503 (service-state, e.g. DB not ready) — not blocking" ;;
        *) fail "Shell endpoint POST ${shell_url} returned ${shell_code} (broken/down shell)" ;;
      esac
      return 0
    fi
    sleep "$sleep_seconds"
  done
  fail "Health endpoint did not become ready at ${url} within ${attempts}s"
}

# Derive the grantee domains from the live grantee profiles so the smoke gate
# auto-covers any newly-added grantee without editing this script.
smoke_domains() {
  python3 - "${LIVE_ROOT}/private" <<'PY'
import sys, glob, json, os
base = sys.argv[1]
seen = []
for path in sorted(glob.glob(os.path.join(base, "utilities", "tools", "fnd-csm", "grantee.*.json"))):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        continue
    for dom in (data.get("domains") or []):
        dom = str(dom).strip().lower()
        if dom and dom not in seen:
            seen.append(dom)
print("\n".join(seen))
PY
}

# Post-deploy gate: prove the public form endpoints actually resolve each grantee
# domain and respond, using side-effect-free probes. This is the check that would
# have caught the silent connect 404 outage. Runs AFTER restart+health on --code.
run_public_form_smoke() {
  [[ -n "$PORT" ]] || fail "No port known for instance ${INSTANCE}"
  local base="http://127.0.0.1:${PORT}"
  local domains
  domains="$(smoke_domains)"
  if [[ -z "$domains" ]]; then
    log "Public-form smoke: no grantee domains found — skipping"
    return 0
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    log "[dry-run] would smoke-test public forms for: $(echo "$domains" | tr '\n' ' ')"
    return 0
  fi
  local failures=0 d code
  while IFS= read -r d; do
    [[ -n "$d" ]] || continue
    # connect: honeypot probe (hp_field set) passes the grantee gate then
    # short-circuits before any persist/SES — must be 200 if the domain resolves.
    code="$(curl -s -m 10 -o /dev/null -w '%{http_code}' -X POST "${base}/__fnd/connect/submit" \
      -H "Host: ${d}" -H "Content-Type: application/json" -H "Accept: application/json" \
      -d "{\"email\":\"smoke@example.com\",\"message\":\"deploy smoke\",\"hp_field\":\"x\",\"domain\":\"${d}\"}" || echo 000)"
    if [[ "$code" != "200" ]]; then
      log "SMOKE FAIL connect ${d}: HTTP ${code} (expected 200 — grantee not resolving?)"
      failures=$((failures + 1))
    fi
    # newsletter: a bad email on a newsletter-enabled domain returns 400
    # invalid_email. A 404 is tolerated here — alias domains (e.g. cvccboard.org)
    # legitimately have no newsletter-admin profile; the grantee-vs-newsletter
    # divergence is caught by the dedicated config-consistency test instead. Only
    # a server error (5xx) or no response (000) fails the gate.
    code="$(curl -s -m 10 -o /dev/null -w '%{http_code}' -X POST "${base}/__fnd/newsletter/subscribe" \
      -H "Host: ${d}" -H "Content-Type: application/json" -H "Accept: application/json" \
      -d "{\"email\":\"not-an-email\",\"domain\":\"${d}\"}" || echo 000)"
    if [[ "$code" == "000" || "$code" -ge 500 ]]; then
      log "SMOKE FAIL newsletter ${d}: HTTP ${code} (server error)"
      failures=$((failures + 1))
    fi
  done <<< "$domains"
  # donate create-order: an empty body trips the missing_amount 400 before any
  # PayPal/profile lookup, so this proves the route is registered + alive.
  local first_domain
  first_domain="$(echo "$domains" | head -n1)"
  code="$(curl -s -m 10 -o /dev/null -w '%{http_code}' -X POST "${base}/__fnd/paypal/create-order" \
    -H "Host: ${first_domain}" -H "Content-Type: application/json" -H "Accept: application/json" -d '{}' || echo 000)"
  if [[ "$code" == "000" || "$code" -ge 500 ]]; then
    log "SMOKE FAIL paypal/create-order: HTTP ${code}"
    failures=$((failures + 1))
  fi
  if [[ "$failures" -gt 0 ]]; then
    fail "Public-form smoke gate failed (${failures} check(s)). The service is live but a public form is broken — roll back or fix before treating this deploy as good."
  fi
  log "Public-form smoke gate passed for all grantee domains"
}

# Report (don't block) per-grantee config gaps — newsletter-admin presence,
# contact forward address, aws_ses identity — derived from the grantee profiles.
# Report-only here so a tooling hiccup can't block a deploy; CI / operators run
# it with --strict to gate on REQUIRED gaps.
run_grantee_config_check() {
  [[ "$DRY_RUN" == "1" ]] && { log "[dry-run] would run grantee config-consistency check"; return 0; }
  local py="${MYCITE_PORTAL_VENV:-/srv/venvs/fnd_portal}/bin/python"
  [[ -x "$py" ]] || py="python3"
  log "Grantee config-consistency (report-only; CI uses --strict):"
  PYTHONPATH="$REPO_ROOT" "$py" -m MyCiteV2.scripts.grantee_config_consistency \
    --private-dir "${LIVE_ROOT}/private" \
    || log "WARN: grantee config-consistency linter did not run cleanly"
}

should_enforce_cts_gis_compile() {
  [[ "$SKIP_CTS_GIS_COMPILE_CHECK" != "1" ]] || return 1
  [[ "$INSTANCE" == "fnd" ]] || return 1
  [[ "$DO_DATA" == "1" || "$DO_PRIVATE" == "1" || "$DO_CODE" == "1" ]] || return 1
  # MOS-backed (2026-05-17 cleanup retired the disk sandbox/cts-gis/sources/ tree):
  # enforce when the MOS authority DB is present, OR the legacy disk sources exist.
  [[ -f "${LIVE_ROOT}/private/mos_authority.sqlite3" || -d "${LIVE_ROOT}/data/sandbox/cts-gis/sources" ]] || return 1
  return 0
}

compile_and_validate_cts_gis() {
  local data_dir="${LIVE_ROOT}/data"
  local private_dir="${LIVE_ROOT}/private"
  # Use the portal venv (deps + MyCiteV2 importable), mirroring run_grantee_config_check.
  local py="${MYCITE_PORTAL_VENV:-/srv/venvs/fnd_portal}/bin/python"
  [[ -x "$py" ]] || py="python3"
  local compile_cmd=(
    env "PYTHONPATH=${REPO_ROOT}" "$py"
    "${REPO_ROOT}/MyCiteV2/scripts/compile_cts_gis_artifact.py"
    --data-dir
    "${data_dir}"
    --private-dir
    "${private_dir}"
    --scope-id
    "${INSTANCE}"
  )
  local validate_cmd=(
    env "PYTHONPATH=${REPO_ROOT}" "$py"
    "${REPO_ROOT}/MyCiteV2/scripts/validate_cts_gis_sources.py"
    --data-dir
    "${data_dir}"
    --private-dir
    "${private_dir}"
    --scope-id
    "${INSTANCE}"
    --require-compiled-match
  )
  log "Compiling CTS-GIS artifact for ${INSTANCE} before deploy"
  run_or_echo "${compile_cmd[@]}"
  log "Validating CTS-GIS compiled freshness for ${INSTANCE}"
  run_or_echo "${validate_cmd[@]}"
}

INSTANCE="fnd"
DO_DATA="0"
DO_PUBLIC="0"
DO_PRIVATE="0"
FORCE_RESTORE_PRIVATE="0"
DO_TOOLS_ONLY="0"
DO_CODE="0"
BUILD_LABEL="manual-update"
SKIP_BUILD_BUMP="0"
SKIP_RESTART="0"
SKIP_HEALTH="0"
SKIP_SMOKE="0"
SKIP_CONFIG_CHECK="0"
DRY_RUN="0"
INCLUDE_TOOL_STATE="0"
SKIP_VERIFY="0"
SKIP_CTS_GIS_COMPILE_CHECK="0"
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
    --force-restore-private)
      # Explicit opt-in for the DESTRUCTIVE deployed->live private restore.
      DO_PRIVATE="1"
      FORCE_RESTORE_PRIVATE="1"
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
      # NOTE: --all intentionally NO LONGER includes --private. The
      # deployed->live private sync clobbers the canonical live store
      # (aws-csm mailbox truth, contacts, PayPal) and must be opted into
      # explicitly via --force-restore-private (disaster restore only).
      DO_DATA="1"
      DO_PUBLIC="1"
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
    --skip-smoke)
      SKIP_SMOKE="1"
      shift
      ;;
    --skip-config-check)
      SKIP_CONFIG_CHECK="1"
      shift
      ;;
    --skip-verify)
      SKIP_VERIFY="1"
      shift
      ;;
    --skip-cts-gis-compile-check)
      SKIP_CTS_GIS_COMPILE_CHECK="1"
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
LIVE_ROOT="/srv/webapps/mycite/${INSTANCE}"
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
  if [[ "$FORCE_RESTORE_PRIVATE" != "1" ]]; then
    fail "Refusing deployed->live private sync. The LIVE store (${LIVE_ROOT}/private) is CANONICAL — it holds the operational truth (aws-csm mailbox routing, provisioned SMTP usernames, contacts, PayPal state). deployed/ is a re-bootstrapped DR skeleton; an 'rsync -a --delete' from it would clobber live and re-introduce the split-brain that silently dropped mail. For a deliberate DISASTER RESTORE, re-run with --force-restore-private. To capture a DR snapshot, rsync live -> deployed (never the reverse)."
  fi
  log "DISASTER RESTORE: --force-restore-private set; overwriting live/private from deployed/private"
  sync_tree "${DEPLOYED_ROOT}/private" "${LIVE_ROOT}/private" "private files (FORCED RESTORE)"
  if [[ "$SKIP_VERIFY" != "1" ]]; then
    verify_sync "${DEPLOYED_ROOT}/private" "${LIVE_ROOT}/private" "private files (FORCED RESTORE)"
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

if should_enforce_cts_gis_compile; then
  compile_and_validate_cts_gis
fi

if [[ "$DO_CODE" == "1" ]]; then
  if [[ "$SKIP_BUILD_BUMP" != "1" ]]; then
    write_build_id "$BUILD_LABEL"
  fi
  if [[ "$SKIP_RESTART" != "1" ]]; then
    restart_service
  fi
  # run_health_check now also POSTs /portal/api/v2/shell (see the function), so a
  # hard-500ing shell fails the deploy. Stale-worker / disk-newer-than-running is
  # caught independently by the healthz source_freshness gate (any code change,
  # incl. a raw git operation on the live tree, not just a --code deploy).
  if [[ "$SKIP_HEALTH" != "1" ]]; then
    run_health_check
  fi
  if [[ "$SKIP_SMOKE" != "1" ]]; then
    run_public_form_smoke
  fi
  if [[ "$SKIP_CONFIG_CHECK" != "1" ]]; then
    run_grantee_config_check
  fi
fi

log "Completed for instance ${INSTANCE}"
