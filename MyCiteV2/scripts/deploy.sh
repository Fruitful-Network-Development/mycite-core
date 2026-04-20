#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPDATE_SCRIPT="${SCRIPT_DIR}/deploy_portal_update.sh"

usage() {
  cat <<'EOF'
Usage:
  ./deploy.sh <all|data|portal> [deploy_portal_update options...]
  ./deploy.sh -- [raw deploy_portal_update options...]

Modes:
  all      Sync deployed data/public/private and deploy portal code.
  data     Sync deployed data/public/private only.
  portal   Deploy portal code only (build bump + restart + health check).

Examples:
  ./deploy.sh all --instance fnd
  ./deploy.sh data --instance fnd
  ./deploy.sh portal --instance fnd
  ./deploy.sh all --instance fnd --dry-run
  ./deploy.sh -- --instance fnd --tools-only --tool cts-gis
EOF
}

fail() {
  printf '[deploy] ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -x "$UPDATE_SCRIPT" ]] || fail "Missing executable ${UPDATE_SCRIPT}"

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

mode="$1"
shift || true

case "$mode" in
  all)
    exec "$UPDATE_SCRIPT" --all "$@"
    ;;
  data)
    exec "$UPDATE_SCRIPT" --data --public --private "$@"
    ;;
  portal|code)
    exec "$UPDATE_SCRIPT" --code "$@"
    ;;
  --)
    exec "$UPDATE_SCRIPT" "$@"
    ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    fail "Unknown mode: ${mode}. Use all, data, portal, or -- for raw options."
    ;;
esac
