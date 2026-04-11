# T-002 Operator runbook — V2 portal deploy truth

This runbook documents the **single shell entrypoint** that checks **repo intent**, **live HTTPS** (public routes), **portal HTML** (authenticated edge or loopback), **effective nginx** semantics, and **systemd** for the FND V2 portal.

## Canonical command

From the **mycite-core** repository root:

```bash
cd /srv/repo/mycite-core
bash scripts/verify_v2_portal_deploy_truth.sh
```

The script is also executable (`scripts/verify_v2_portal_deploy_truth.sh`) if your checkout preserves execute bits.

## What it checks

1. **Repo — `portal.html` and static** under `MYCITE_CORE`  
   - Markers: `shell-template: v2-composition`, `data-portal-shell-driver="v2-composition"`, `href="/portal/static/portal.css"`, `v2_portal_shell.js`, `build={{ portal_build_id }}` in the template comment.  
   - `v2_portal_shell.js` exists and is non-empty.

2. **Repo — nginx intent file** under `SRV_INFRA`  
   - Default path: `/srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`  
   - Asserts presence of `location = /healthz` → `127.0.0.1:6101/healthz`, `location ^~ /portal/static/`, and `location ^~ /portal`.

3. **Live HTTPS (edge, no browser session)** — `PORTAL_BASE_URL` (default `https://portal.fruitfulnetworkdevelopment.com`)  
   - `GET /portal/static/portal.css` → HTTP 200  
   - `GET /portal/static/v2_portal_shell.js` → HTTP 200  
   - `GET /healthz` → HTTP 200, JSON includes `mycite.v2.portal.health.v1`, `v2_native`, `static_url_path` + `/portal/static`, and **`ok` must be JSON `true`** (matches `app.py` `_build_health` / native host expectations).

4. **Live portal HTML markers**  
   - Tries `GET /portal/system` on the public URL. **OAuth2 often returns HTTP 200 with a sign-in HTML page**, which is **not** the V2 shell; the script treats that as **not** portal HTML.  
   - If the edge body does not contain `shell-template: v2-composition`, it falls back to **loopback** `http://127.0.0.1:6101/portal/system` when that host answers `GET /healthz` (typical **on-portal-host** run).  
   - Override loopback with `VERIFY_DEPLOY_TRUTH_LOOPBACK_BASE` (e.g. SSH tunnel).  
   - For **authenticated edge** HTML checks, you would need a browser session cookie wired into curl (not built into the script); loopback on the portal host is the supported default.

5. **On-host — systemd (FND V2 portal)**  
   - Unit name (default): **`mycite-v2-fnd-portal.service`** (`PORTAL_SYSTEMD_UNIT` to override).  
   - Runs `systemctl status` and `systemctl show` for: **`ActiveState`**, **`SubState`**, **`FragmentPath`**.  
   - Expects `ActiveState=active` and `SubState=running`.

6. **On-host — nginx effective configuration**  
   - Runs `sudo nginx -T` (passwordless sudo) or `nginx -T` if permitted.  
   - Greps the full dump for: `server_name portal.fruitfulnetworkdevelopment.com`, `location = /healthz`, `proxy_pass` to `127.0.0.1:6101/healthz`, `location ^~ /portal/static/`, `location ^~ /portal`, and presence of `127.0.0.1:6101`.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MYCITE_CORE` | parent of `scripts/` | Repo root containing `MyCiteV2/...` |
| `SRV_INFRA` | `/srv/repo/srv-infra` | Repo root containing `nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf` |
| `PORTAL_BASE_URL` | `https://portal.fruitfulnetworkdevelopment.com` | Live HTTPS base |
| `PORTAL_SYSTEMD_UNIT` | `mycite-v2-fnd-portal.service` | systemd unit to inspect |
| `FND_PORTAL_LOOPBACK` | `http://127.0.0.1:6101` | Default loopback for HTML when edge is not portal shell |
| `VERIFY_DEPLOY_TRUTH_LOOPBACK_BASE` | (empty) | Force loopback base URL for HTML checks |
| `VERIFY_DEPLOY_TRUTH_SKIP_HOST` | `0` | Set to `1` to skip systemd + `nginx -T` (laptop / no sudo) |
| `VERIFY_DEPLOY_TRUTH_ALLOW_PARTIAL` | `0` | Set to `1` with `SKIP_HOST=1` to exit 0 after repo+live only (not verifier closure) |

## Running locally (laptop / CI without portal host)

- Repo + live static + live `/healthz` still run if paths and network are correct.  
- **HTML markers** require loopback to `6101` or another reachable portal bind, or the check fails.  
- **systemd / nginx -T** require the portal machine and privileges.

For a **deliberately incomplete** run (e.g. CI that only has HTTPS to production):

```bash
cd /srv/repo/mycite-core
VERIFY_DEPLOY_TRUTH_SKIP_HOST=1 VERIFY_DEPLOY_TRUTH_ALLOW_PARTIAL=1 \
  bash scripts/verify_v2_portal_deploy_truth.sh
```

Exit code **4** if `SKIP_HOST=1` without `ALLOW_PARTIAL=1` (signals “not full deploy truth”).

## Running on the portal host (verifier-style)

```bash
cd /srv/repo/mycite-core
bash scripts/verify_v2_portal_deploy_truth.sh
```

Requires:

- `systemctl` available and unit `mycite-v2-fnd-portal.service` active.  
- `nginx -T` via `sudo -n` or direct permission.

## Manual trust checks (optional)

Compare repo nginx to enabled site (paths may vary):

```bash
grep -nE 'healthz|6101|6203|portal/static|location \^~ /portal' \
  /srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf
sudo nginx -T 2>/dev/null | grep -nF 'location = /healthz' | head
```

## Failure modes (short)

| Symptom | Likely meaning |
|---------|------------------|
| `healthz` `ok=false` or HTTP 503 | Host data/AWS profile/static bundle unhealthy per `app.py` — not a client-only issue. |
| Edge static not 200 | CDN/nginx/static upstream or TLS problem. |
| HTML check fails, loopback unset | No session on edge and no `6101` from this machine — run on host or set `VERIFY_DEPLOY_TRUTH_LOOPBACK_BASE`. |
| `nginx -T` fails | Missing sudo or not nginx host. |
| systemd not `active (running)` | Portal service down or wrong unit name. |
| Exit 4 | Host checks skipped without partial allowance — treat as **blocked / incomplete** for T-002 closure. |

## Related task metadata

- Task: `tasks/T-002-deploy-truth-automation.yaml`  
- Implementation report: `reports/T-002-implementation.md`  
- Verifier report (independent): `reports/T-002-verification.md` (not authored here)
