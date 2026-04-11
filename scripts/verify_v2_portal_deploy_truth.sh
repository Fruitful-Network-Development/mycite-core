#!/usr/bin/env bash
# Deterministic deploy-truth checks: repo markers, live HTTPS (static + health + portal HTML),
# on-host nginx semantics vs srv-infra repo intent, systemd unit identity.
# Usage: from repo root: bash scripts/verify_v2_portal_deploy_truth.sh
# Exit: 0 all checks passed; 1 verification failed;
#   4 VERIFY_DEPLOY_TRUTH_SKIP_HOST=1 without VERIFY_DEPLOY_TRUTH_ALLOW_PARTIAL=1 (incomplete / not verifier closure)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MYCITE_CORE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MYCITE_CORE="${MYCITE_CORE:-$MYCITE_CORE_ROOT}"
SRV_INFRA="${SRV_INFRA:-/srv/repo/srv-infra}"
PORTAL_BASE_URL="${PORTAL_BASE_URL:-https://portal.fruitfulnetworkdevelopment.com}"
PORTAL_SYSTEMD_UNIT="${PORTAL_SYSTEMD_UNIT:-mycite-v2-fnd-portal.service}"
FND_PORTAL_LOOPBACK="${FND_PORTAL_LOOPBACK:-http://127.0.0.1:6101}"
SKIP_HOST="${VERIFY_DEPLOY_TRUTH_SKIP_HOST:-0}"
ALLOW_PARTIAL="${VERIFY_DEPLOY_TRUTH_ALLOW_PARTIAL:-0}"

REPO_NGINX="${SRV_INFRA}/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf"
PORTAL_HTML="${MYCITE_CORE}/MyCiteV2/instances/_shared/portal_host/templates/portal.html"
PORTAL_JS="${MYCITE_CORE}/MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js"
HEALTH_SCHEMA="mycite.v2.portal.health.v1"

usage() {
  sed -n '1,80p' "$0" | sed -n '2,/^[^#]/p' | head -n 20
}

log() { printf '%s\n' "$*"; }
die() { log "ERROR: $*"; exit 1; }
warn() { log "WARN: $*"; }

need_file() {
  local f="$1"
  [[ -f "$f" ]] || die "missing file: $f (set MYCITE_CORE / SRV_INFRA?)"
}

curl_code() {
  local url="$1"
  shift
  curl -sS -o /dev/null -w '%{http_code}' "$@" "$url" 2>/dev/null || printf '000'
}

curl_body() {
  local url="$1"
  shift
  curl -sS "$@" "$url"
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  local msg="$3"
  [[ "$haystack" == *"$needle"* ]] || die "$msg (expected substring: ${needle:0:80}...)"
}

check_repo_templates() {
  log "== repo: portal.html markers =="
  need_file "$PORTAL_HTML"
  local t
  t="$(cat "$PORTAL_HTML")"
  assert_contains "$t" 'shell-template: v2-composition' "portal.html missing shell-template marker"
  assert_contains "$t" 'data-portal-shell-driver="v2-composition"' "portal.html missing data-portal-shell-driver"
  assert_contains "$t" 'href="/portal/static/portal.css"' "portal.html missing static css href"
  assert_contains "$t" 'v2_portal_shell.js' "portal.html missing v2_portal_shell.js script surface"
  assert_contains "$t" 'build={{ portal_build_id }}' "portal.html missing build= shell comment"
  log "== repo: v2_portal_shell.js present =="
  need_file "$PORTAL_JS"
  [[ -s "$PORTAL_JS" ]] || die "v2_portal_shell.js is empty"
  log "repo template/static checks: OK"
}

check_repo_nginx_intent_file() {
  log "== repo: srv-infra nginx intent file readable =="
  need_file "$REPO_NGINX"
  grep -Fq 'location = /healthz' "$REPO_NGINX" || die "repo nginx: missing healthz location"
  grep -Fq '127.0.0.1:6101/healthz' "$REPO_NGINX" || die "repo nginx: healthz must proxy to 6101"
  grep -Fq 'location ^~ /portal/static/' "$REPO_NGINX" || die "repo nginx: missing portal static location"
  grep -Fq 'location ^~ /portal' "$REPO_NGINX" || die "repo nginx: missing portal shell location"
  log "repo nginx intent file: OK"
}

check_live_static_and_health() {
  log "== live: HTTPS static + healthz (edge, no portal session required) =="
  local css="${PORTAL_BASE_URL}/portal/static/portal.css"
  local js="${PORTAL_BASE_URL}/portal/static/v2_portal_shell.js"
  local hz="${PORTAL_BASE_URL}/healthz"
  local c
  c="$(curl_code "$css" -L --max-time 25)" || die "curl failed: $css"
  [[ "$c" == "200" ]] || die "expected HTTP 200 from $css got $c"
  c="$(curl_code "$js" -L --max-time 25)" || die "curl failed: $js"
  [[ "$c" == "200" ]] || die "expected HTTP 200 from $js got $c"

  local health_raw
  health_raw="$(curl_body "$hz" -L --max-time 25)" || die "curl failed: $hz"
  printf '%s' "$health_raw" | grep -q "$HEALTH_SCHEMA" || die "healthz JSON missing schema ${HEALTH_SCHEMA}"
  printf '%s' "$health_raw" | grep -q '"host_shape"' && printf '%s' "$health_raw" | grep -q 'v2_native' \
    || die "healthz missing host_shape v2_native"
  printf '%s' "$health_raw" | grep -q 'static_url_path' && printf '%s' "$health_raw" | grep -q '/portal/static' \
    || die "healthz missing static_url_path /portal/static"
  if command -v python3 >/dev/null 2>&1; then
    local ok_line
    ok_line="$(printf '%s' "$health_raw" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("ok="+str(d.get("ok")))')" \
      || die "healthz body is not valid JSON"
    [[ "$ok_line" == "ok=True" ]] || die "healthz reports ok=false ($ok_line) — inspect datum/aws/static on host"
  fi
  local hz_code
  hz_code="$(curl_code "$hz" -L --max-time 25)" || true
  [[ "$hz_code" == "200" ]] || die "healthz HTTP status expected 200 got $hz_code"
  log "live static + healthz: OK"
}

# HTML shell markers: edge /portal is usually OAuth-wrapped; prefer 200 edge, else loopback on host.
check_live_portal_html() {
  log "== live: portal HTML (markers) =="
  local edge="${PORTAL_BASE_URL}/portal/system"
  local tmp
  tmp="$(mktemp)"
  local code
  code="$(curl -sS -L --max-time 25 -o "$tmp" -w '%{http_code}' "$edge" 2>/dev/null || printf '000')"
  local body=""
  local edge_ok=0
  if [[ "$code" == "200" ]] && [[ -s "$tmp" ]]; then
    local cand
    cand="$(cat "$tmp")"
    if printf '%s' "$cand" | grep -Fq "shell-template: v2-composition"; then
      body="$cand"
      edge_ok=1
      log "edge /portal/system returned authenticated portal HTML"
    else
      warn "edge /portal/system HTTP 200 but body is not V2 portal shell (typical: oauth2 sign-in HTML without session)"
    fi
  else
    warn "edge /portal/system HTTP $code"
  fi
  rm -f "$tmp"
  if [[ "$edge_ok" != "1" ]]; then
    local lb="${VERIFY_DEPLOY_TRUTH_LOOPBACK_BASE:-}"
    if [[ -z "$lb" ]]; then
      if curl -sS -o /dev/null --max-time 2 "$FND_PORTAL_LOOPBACK/healthz" 2>/dev/null; then
        lb="$FND_PORTAL_LOOPBACK"
        log "using auto-selected loopback $lb for HTML markers"
      fi
    fi
    [[ -n "$lb" ]] || die "cannot verify portal HTML: edge is not authenticated portal shell; set VERIFY_DEPLOY_TRUTH_LOOPBACK_BASE=http://127.0.0.1:6101 (on-host) or pass a session cookie via curl wrapper (see runbook)"
    body="$(curl_body "${lb}/portal/system" --max-time 25)" || die "loopback portal/system failed"
    log "checked HTML markers via loopback ${lb}/portal/system"
  fi
  assert_contains "$body" "shell-template: v2-composition" "portal HTML missing shell-template marker"
  assert_contains "$body" "data-portal-shell-driver=\"v2-composition\"" "portal HTML missing shell driver attr"
  assert_contains "$body" 'href="/portal/static/portal.css"' "portal HTML missing css href"
  assert_contains "$body" "v2_portal_shell.js" "portal HTML missing v2_portal_shell.js"
  assert_contains "$body" "build=" "portal HTML missing build= marker"
  log "portal HTML markers: OK"
}

check_systemd_unit() {
  log "== on-host: systemd ${PORTAL_SYSTEMD_UNIT} =="
  if [[ "$SKIP_HOST" == "1" ]]; then
    warn "VERIFY_DEPLOY_TRUTH_SKIP_HOST=1 — skipping systemd and nginx host checks"
    return 0
  fi
  if ! command -v systemctl >/dev/null 2>&1; then
    die "systemctl not available (host checks blocked)"
  fi
  systemctl status "$PORTAL_SYSTEMD_UNIT" --no-pager -l || die "systemctl status failed for $PORTAL_SYSTEMD_UNIT"
  local state sub frag
  state="$(systemctl show "$PORTAL_SYSTEMD_UNIT" -p ActiveState --value)"
  sub="$(systemctl show "$PORTAL_SYSTEMD_UNIT" -p SubState --value)"
  frag="$(systemctl show "$PORTAL_SYSTEMD_UNIT" -p FragmentPath --value)"
  log "systemd ActiveState=${state} SubState=${sub} FragmentPath=${frag}"
  [[ "$state" == "active" ]] || die "unit not active (ActiveState=$state)"
  [[ "$sub" == "running" ]] || die "unit not running (SubState=$sub)"
  log "systemd: OK"
}

nginx_dump() {
  if [[ "$SKIP_HOST" == "1" ]]; then
    return 1
  fi
  if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    sudo nginx -T
    return $?
  fi
  if nginx -T 2>/dev/null; then
    return 0
  fi
  return 1
}

check_nginx_effective_vs_repo() {
  log "== on-host: nginx effective config (semantic grep vs repo intent) =="
  if [[ "$SKIP_HOST" == "1" ]]; then
    return 0
  fi
  local eff
  eff="$(mktemp)"
  if ! nginx_dump >"$eff" 2>/dev/null; then
    die "cannot run nginx -T (need host access / passwordless sudo for nginx); for laptop-only repo+live use VERIFY_DEPLOY_TRUTH_SKIP_HOST=1 VERIFY_DEPLOY_TRUTH_ALLOW_PARTIAL=1"
  fi
  grep -Fq "server_name portal.fruitfulnetworkdevelopment.com" "$eff" || die "nginx -T: missing portal server_name"
  grep -Fq "location = /healthz" "$eff" || die "nginx -T: missing exact healthz location"
  grep -Fq "127.0.0.1:6101" "$eff" || die "nginx -T: missing 6101 upstream (FND V2 portal)"
  grep -Fq "proxy_pass http://127.0.0.1:6101/healthz" "$eff" \
    || grep -Fq "proxy_pass http://127.0.0.1:6101/healthz;" "$eff" \
    || die "nginx -T: healthz must proxy_pass to 127.0.0.1:6101/healthz"
  grep -Fq "location ^~ /portal/static/" "$eff" || die "nginx -T: missing portal static location"
  grep -Fq "location ^~ /portal" "$eff" || die "nginx -T: missing portal location"
  # Repo file must remain aligned with these semantics (already checked); cross-check key tokens exist in both.
  local sig
  sig="$(grep -vE '^\s*#' "$REPO_NGINX" | tr -s ' \t' ' ')"
  assert_contains "$sig" "127.0.0.1:6101" "repo nginx intent missing 6101"
  assert_contains "$sig" "127.0.0.1:6203" "repo nginx intent missing 6203 (TFF upstream)"
  log "nginx effective vs intent (grep-level): OK"
  rm -f "$eff"
}

main() {
  case "${1:-}" in
    -h|--help) usage; exit 0 ;;
  esac

  need_file "${MYCITE_CORE}/MyCiteV2/instances/_shared/portal_host/app.py"

  check_repo_templates
  check_repo_nginx_intent_file
  check_live_static_and_health
  check_live_portal_html
  check_systemd_unit
  check_nginx_effective_vs_repo

  if [[ "$SKIP_HOST" == "1" ]] && [[ "$ALLOW_PARTIAL" != "1" ]]; then
    log ""
    log "INCOMPLETE: VERIFY_DEPLOY_TRUTH_SKIP_HOST=1 without VERIFY_DEPLOY_TRUTH_ALLOW_PARTIAL=1 (exit 4)."
    exit 4
  fi

  log ""
  log "All deploy-truth checks passed."
}

main "$@"
