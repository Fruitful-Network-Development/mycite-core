# T-002 Implementation report — deploy truth automation

This report follows `agent/implementer.md` and `agent/constraints.md`: **repo and automation are documented here; verifier-owned live closure is not claimed.**

## 1. Files changed

| File | Change type | Why |
|------|-------------|-----|
| `scripts/verify_v2_portal_deploy_truth.sh` | **diagnostic / deploy-config** | Single deterministic bash entrypoint: repo markers, repo nginx intent path, live HTTPS (static + `/healthz`), portal HTML (edge or loopback), `systemctl`, `nginx -T` semantic greps. |
| `reports/T-002-operator-runbook.md` | **diagnostic** | Operator instructions, env vars, failure modes, systemd unit identity. |
| `reports/T-002-implementation.md` | **diagnostic** | This file. |

No changes to `app.py`, `portal.html`, `v2_portal_shell.js`, integration tests, or `srv-infra` nginx content: those paths were **read-only references** for acceptance alignment.

## 2. Why each file changed

- **Script:** Satisfies acceptance for a **shell-invokable** path that fails non-zero when checks fail, without replacing deploy/live checks with mocked-only tests. Host checks call real `systemctl` and `nginx -T`. Live checks use real `curl` against HTTPS. Repo checks read real template files.  
- **Runbook:** Task-required operator doc for local vs on-host runs and env vars.  
- **Implementation report:** Task-required record of files, commands, and gaps.

## 3. Commands run

### 3.1 Repo test baseline (exact per lead handoff)

```bash
cd /srv/repo/mycite-core
for d in MyCiteV2/tests/adapters MyCiteV2/tests/architecture MyCiteV2/tests/contracts MyCiteV2/tests/integration MyCiteV2/tests/unit; do
  echo "== $d =="
  PYTHONPATH=/srv/repo/mycite-core /srv/venvs/fnd_portal/bin/python3 -m unittest discover -s "$d" -p "test*.py" -v || exit 1
done
```

**Result:** Exit code **0** (all five directories completed; integration includes `test_v2_native_portal_host.py`).

### 3.2 Task `suggested_commands` — pytest

```bash
cd /srv/repo/mycite-core && PYTHONPATH=/srv/repo/mycite-core /srv/venvs/fnd_portal/bin/python3 -m pytest MyCiteV2/tests
```

**Result:** **Not run** — `/srv/venvs/fnd_portal/bin/python3` reports `No module named pytest` in this environment. **Unresolved:** install `pytest` into that venv or document an alternate venv for pytest if the project expects it.

### 3.3 Deploy-truth script (implementer smoke on this workspace)

```bash
cd /srv/repo/mycite-core
bash scripts/verify_v2_portal_deploy_truth.sh
```

**Result:** Exit code **0** on the machine where this command was executed (portal-capable environment: live HTTPS checks passed; loopback `127.0.0.1:6101` used for HTML markers because edge `/portal/system` returned OAuth sign-in HTML; `systemctl` and `nginx -T` checks passed).

**Captured live sample (edge `/healthz`, for schema/shape only — not a verifier verdict):**

```text
$ curl -sS https://portal.fruitfulnetworkdevelopment.com/healthz | python3 -c "import json,sys; d=json.load(sys.stdin); print('ok', d.get('ok'), 'schema', d.get('schema'), 'host_shape', d.get('host_shape'))"
ok True schema mycite.v2.portal.health.v1 host_shape v2_native
```

**Important:** This implementation report **does not** substitute for `reports/T-002-verification.md`. The verifier must rerun the script **independently** and capture **their own** outputs for closure.

## 4. Tests run

- **unittest** discover across the five `MyCiteV2/tests/*` subtrees (see §3.1): **pass**.  
- **pytest:** unavailable in `fnd_portal` venv (see §3.2).

## 5. Deploy actions taken

**None.** Only repository scripts and reports were added. No nginx reload, no systemd restart, no production config edits.

## 6. What still requires independent verification

- Verifier re-run of `bash scripts/verify_v2_portal_deploy_truth.sh` with captured stdout/stderr.  
- Verifier judgment that **edge** behavior (OAuth vs portal HTML) matches operational expectations for their environment (script documents loopback fallback).  
- Optional: install `pytest` and record `pytest MyCiteV2/tests` in the verification report if the project standardizes on pytest for CI.

## 7. Remaining gaps / unresolved risks

1. **pytest missing** in `/srv/venvs/fnd_portal` — task suggested command not reproducible there without adding the dependency.  
2. **Edge `/portal/system` without session** returns sign-in HTML with HTTP 200; the script **requires** either real portal HTML at the edge or a working **loopback** (or future cookie-based curl). Operators must understand this is **not** a mock; it reflects nginx/oauth2 behavior.  
3. **nginx -T** checks are **semantic grep** assertions, not a full structural diff against the repo file (includes are expanded in `-T` output). Misconfiguration that preserves the grepped tokens could still be wrong — manual `diff` remains advisable for ambiguous incidents.  
4. **TFF portal** (`6203`, `mycite-v2-tff-portal.service`) is referenced in repo nginx but **not** exhaustively validated by this script (FND-first scope per handoff).

## 8. Evidence classes (per `agent/constraints.md`)

1. **Repo findings:** Task-listed files align with script expectations (`portal.html` markers, `app.py` health schema constant `mycite.v2.portal.health.v1`, nginx repo file paths/ports).  
2. **Changes made:** Listed in §1.  
3. **Tests run:** §4.  
4. **Deploy findings:** No deploy performed (§5).  
5. **Live verification:** Sample `/healthz` snippet in §3.3; full script log is **not** pasted here to avoid over-claiming — verifier captures authoritative logs.  
6. **Remaining gaps:** §7.

## 9. Recommended next status

**`in_progress` / blocked until verifier** — Keep T-002 **open** until `reports/T-002-verification.md` contains an **independent** full run of `scripts/verify_v2_portal_deploy_truth.sh` (and lead compares repo, host, and live sections per task `closure_rule`). Repo automation is in place; **closure is verifier-owned.**

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

# T-002 Verification report — independent deploy-truth pass

Verifier role: assume implementer output may be wrong; evidence below is from **this** run only (`agent/constraints.md` §5, §9; `agent/verifier.md`; `tasks/T-002-deploy-truth-automation.yaml` `verification_requirements`).

---

## 1. Exact command(s) used (full invocation, cwd)

**Primary (documented deploy-truth entrypoint, clean context: initial cwd `/tmp`):**

```bash
cd /tmp && ( cd /srv/repo/mycite-core && bash scripts/verify_v2_portal_deploy_truth.sh ) 2>&1; echo "EXIT_CODE=$?"
```

**Supplemental (evidence only; not substitutes for the script):**

```bash
cd /tmp && ( sudo nginx -T 2>&1 ) | awk '/server_name portal.fruitfulnetworkdevelopment.com/,/^}/' | head -n 250
```

```bash
cd /tmp && curl -sS -D- -o /tmp/t002_system.body --max-time 25 'https://portal.fruitfulnetworkdevelopment.com/portal/system' | head -n 40 && head -n 30 /tmp/t002_system.body
```

```bash
cd /tmp && curl -sS -I --max-time 25 'https://portal.fruitfulnetworkdevelopment.com/portal/static/portal.css'
cd /tmp && curl -sS -I --max-time 25 'https://portal.fruitfulnetworkdevelopment.com/portal/static/v2_portal_shell.js'
```

```bash
cd /tmp && curl -sS -D- --max-time 25 'https://portal.fruitfulnetworkdevelopment.com/healthz' | head -n 25
cd /tmp && curl -sS --max-time 25 'https://portal.fruitfulnetworkdevelopment.com/healthz' | python3 -m json.tool
```

```bash
cd /tmp && curl -sS --max-time 25 'https://portal.fruitfulnetworkdevelopment.com/portal/system' | grep -n 'shell-template: v2-composition\|build:' | head -n 20 || true
cd /tmp && curl -sS --max-time 25 'http://127.0.0.1:6101/portal/system' | grep -n 'shell-template: v2-composition\|build:' | head -n 20
```

```bash
systemctl show mycite-v2-fnd-portal.service -p Id,ActiveState,SubState,FragmentPath,MainPID,ExecStart --no-pager
```

---

## 2. Exact captured stdout/stderr — deploy-truth verification run

**Command:**

`cd /tmp && ( cd /srv/repo/mycite-core && bash scripts/verify_v2_portal_deploy_truth.sh ) 2>&1; echo "EXIT_CODE=$?"`

**Stdout/stderr (verbatim):**

```
== repo: portal.html markers ==
== repo: v2_portal_shell.js present ==
repo template/static checks: OK
== repo: srv-infra nginx intent file readable ==
repo nginx intent file: OK
== live: HTTPS static + healthz (edge, no portal session required) ==
live static + healthz: OK
== live: portal HTML (markers) ==
WARN: edge /portal/system HTTP 200 but body is not V2 portal shell (typical: oauth2 sign-in HTML without session)
using auto-selected loopback http://127.0.0.1:6101 for HTML markers
checked HTML markers via loopback http://127.0.0.1:6101/portal/system
portal HTML markers: OK
== on-host: systemd mycite-v2-fnd-portal.service ==
● mycite-v2-fnd-portal.service - MyCite V2 Fruitful Network Development portal
     Loaded: loaded (/etc/systemd/system/mycite-v2-fnd-portal.service; enabled; preset: enabled)
    Drop-In: /etc/systemd/system/mycite-v2-fnd-portal.service.d
             └─override.conf
     Active: active (running) since Sat 2026-04-11 00:45:09 UTC; 2h 16min ago
 Invocation: c589398e81a54203b3935e49b8120179
   Main PID: 48181 (gunicorn)
      Tasks: 4 (limit: 1126)
     Memory: 28.9M (peak: 58.4M, swap: 42M, swap peak: 42.3M)
        CPU: 1.562s
     CGroup: /system.slice/mycite-v2-fnd-portal.service
             ├─48181 /srv/venvs/fnd_portal/bin/python3 /srv/venvs/fnd_portal/bin/gunicorn --workers 2 --bind 127.0.0.1:6101 MyCiteV2.instances._shared.portal_host.app:app
             ├─48184 /srv/venvs/fnd_portal/bin/python3 /srv/venvs/fnd_portal/bin/gunicorn --workers 2 --bind 127.0.0.1:6101 MyCiteV2.instances._shared.portal_host.app:app
             └─48186 /srv/venvs/fnd_portal/bin/python3 /srv/venvs/fnd_portal/bin/gunicorn --workers 2 --bind 127.0.0.1:6101 MyCiteV2.instances._shared.portal_host.app:app

Apr 11 00:45:09 ip-172-31-21-63 systemd[1]: Started mycite-v2-fnd-portal.service - MyCite V2 Fruitful Network Development portal.
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48181]: [2026-04-11 00:45:09 +0000] [48181] [INFO] Starting gunicorn 25.3.0
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48181]: [2026-04-11 00:45:09 +0000] [48181] [INFO] Listening at: http://127.0.0.1:6101 (48181)
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48181]: [2026-04-11 00:45:09 +0000] [48181] [INFO] Using worker: sync
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48184]: [2026-04-11 00:45:09 +0000] [48184] [INFO] Booting worker with pid: 48184
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48186]: [2026-04-11 00:45:09 +0000] [48186] [INFO] Booting worker with pid: 48186
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48181]: [2026-04-11 00:45:09 +0000] [48181] [INFO] Control socket listening at /home/admin/.gunicorn/gunicorn.ctl
systemd ActiveState=active SubState=running FragmentPath=/etc/systemd/system/mycite-v2-fnd-portal.service
systemd: OK
== on-host: nginx effective config (semantic grep vs repo intent) ==
nginx effective vs intent (grep-level): OK

All deploy-truth checks passed.
EXIT_CODE=0
```

---

## 3. Explicit mapping — task `acceptance` → pass/fail (with cited evidence)

| # | Acceptance bullet | Pass/Fail | Evidence |
|---|---------------------|-----------|----------|
| 1 | A single documented command checks template markers, static assets, health output, nginx routing target, and running service identity. | **Pass** | Script log §2: repo blocks (`== repo: portal.html markers ==`, `repo nginx intent file: OK`), live (`live static + healthz: OK`, `portal HTML markers: OK`), host (`systemd: OK`, `nginx effective vs intent (grep-level): OK`). |
| 2 | The command fails non-zero when template markers, asset routes, or health expectations are missing. | **Pass (by construction + green run)** | Script uses `set -euo pipefail` and `die` on failures (`scripts/verify_v2_portal_deploy_truth.sh`); §2 shows `EXIT_CODE=0`. Negative paths were **not** mutated/tested on production in this pass. |
| 3 | The command checks live `/portal/system`, `/portal/static/portal.css`, `/portal/static/v2_portal_shell.js`, and `/healthz`. | **Pass** | §2: `live static + healthz: OK`; `== live: portal HTML (markers) ==` with edge warn then loopback success. §4–5 document edge vs loopback HTTP for `/portal/system`. |
| 4 | The command or companion step checks actual on-host nginx config and actual running systemd unit state. | **Pass** | §2: full `systemctl status` output; `nginx effective vs intent (grep-level): OK` (from real `nginx -T` inside script). §6: additional `nginx -T` excerpt. |
| 5 | The implementation report includes exact files added or changed. | **Pass** | `reports/T-002-implementation.md` §1 table lists `scripts/verify_v2_portal_deploy_truth.sh`, runbook, implementation report (independent read; not used as live proof). |
| 6 | The verification report includes exact command output from an independent verification pass. | **Pass** | This file §1–2. |

**`verification_requirements` (task YAML):**

| Requirement | Pass/Fail | Evidence |
|-------------|-----------|----------|
| Verifier must rerun the documented deploy-truth command independently. | **Pass** | §1–2: run from `/tmp`, full transcript. |
| Verifier must compare repo nginx intent against actual host nginx configuration. | **Pass** | §6 repo cite + §6 host `nginx -T` excerpt; routing tokens align for `/healthz`, `/portal/static/`, `^~ /portal`, `127.0.0.1:6101` / `6203`. |
| Verifier must refuse closure if any live endpoint disagrees with repo intent. | **Pass** | §4–5: public static + `/healthz` match repo intent (200, correct content types, health schema `mycite.v2.portal.health.v1`, `host_shape` `v2_native`, `static_url_path` `/portal/static`, `ok` true). Edge `/portal/system` is OAuth sign-in HTML (expected for `auth_request` on `location ^~ /portal` in repo nginx); loopback shows V2 shell markers — **not** a repo/live contradiction. |

---

## 4. Host nginx: actual effective config vs repo intent (V2 portal + `/healthz`)

**Repo intent (authoritative path in this workspace):**  
`/srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`

Relevant excerpts (repo):

- `location = /healthz` → `proxy_pass http://127.0.0.1:6101/healthz;` (lines 42–45 in repo file).
- `location ^~ /portal/static/` → `auth_request off;` … `set $portal_upstream http://127.0.0.1:6101;` / TFF `6203` … `proxy_pass $portal_upstream;` (lines 167–184).
- `location ^~ /portal` → OAuth + same `6101`/`6203` upstream (lines 186–213).

**On-host effective configuration (`sudo nginx -T`, excerpt from first HTTPS `server` for `portal.fruitfulnetworkdevelopment.com`; command §1):**

```
    server_name portal.fruitfulnetworkdevelopment.com;

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/portal.fruitfulnetworkdevelopment.com/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/portal.fruitfulnetworkdevelopment.com/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot

    # Shared assets (icons/logos/graphics) from /srv/_shared/assets/*
    include /etc/nginx/sites-available/snippets/shared-assets.conf;

    # oauth2-proxy endpoints (served by portal oauth2-proxy on 127.0.0.1:4181)
    location ^~ /oauth2/ {
        proxy_pass http://127.0.0.1:4181;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;

        # oauth2-proxy uses this to know where to send users back to
        proxy_set_header X-Auth-Request-Redirect $request_uri;

        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # internal auth subrequest endpoint for nginx auth_request
    location = /oauth2/auth {
        internal;
        proxy_pass http://127.0.0.1:4181/oauth2/auth;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_set_header X-Original-URI $request_uri;
        proxy_set_header Content-Length "";
        proxy_pass_request_body off;
    }

    # keep healthz public (no auth). Intentionally targets V2 native FND portal (6101), not legacy 5101.
    location = /healthz {
        auth_request off;
        proxy_pass http://127.0.0.1:6101/healthz;
        include /etc/nginx/sites-available/snippets/proxy_common.conf;

        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # Default: send "/" to the authenticated portal shell
    location = / {
        return 302 /portal;
    }

    # Legacy FND-specific admin bridge is retired; portal-native admin routes are the canonical surface.
    location ^~ /portal/api/admin/fnd/ {
        auth_request /oauth2/auth;
        error_page 401 = /oauth2/sign_in;
        access_log /var/log/nginx/portal-admin-fnd-access.log combined;

        auth_request_set $portal_user  $upstream_http_x_auth_request_user;
        auth_request_set $portal_username $upstream_http_x_auth_request_preferred_username;
        auth_request_set $portal_roles $upstream_http_x_auth_request_groups;

        proxy_set_header X-Portal-User  $portal_user;
        proxy_set_header X-Portal-Username $portal_username;
        proxy_set_header X-Portal-Roles $portal_roles;
        proxy_set_header X-Request-Id $request_id;

        return 410;
    }

    # PayPal admin APIs — legacy path still routed to V1-era fnd_portal (5101). Canonical V2 admin JSON is under /portal/api/v2/.
    location ^~ /portal/api/admin/paypal/ {
        auth_request /oauth2/auth;
        error_page 401 = /oauth2/sign_in;
        access_log /var/log/nginx/portal-admin-paypal-access.log combined;

        auth_request_set $portal_user  $upstream_http_x_auth_request_user;
        auth_request_set $portal_username $upstream_http_x_auth_request_preferred_username;
        auth_request_set $portal_roles $upstream_http_x_auth_request_groups;

        proxy_set_header X-Portal-User  $portal_user;
        proxy_set_header X-Portal-Username $portal_username;
        proxy_set_header X-Portal-Roles $portal_roles;
        proxy_set_header X-Request-Id $request_id;

        proxy_pass http://127.0.0.1:5101;
        include /etc/nginx/sites-available/snippets/proxy_common.conf;

        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # AWS admin APIs — legacy path still routed to V1-era fnd_portal (5101). Canonical V2 AWS tools use /portal/api/v2/admin/aws/* via location ^~ /portal below (6101/6203).
    location ^~ /portal/api/admin/aws/ {
        auth_request /oauth2/auth;
        error_page 401 = /oauth2/sign_in;
        access_log /var/log/nginx/portal-admin-aws-access.log combined;

        auth_request_set $portal_user  $upstream_http_x_auth_request_user;
        auth_request_set $portal_username $upstream_http_x_auth_request_preferred_username;
        auth_request_set $portal_roles $upstream_http_x_auth_request_groups;

        proxy_set_header X-Portal-User  $portal_user;
        proxy_set_header X-Portal-Username $portal_username;
        proxy_set_header X-Portal-Roles $portal_roles;
        proxy_set_header X-Request-Id $request_id;

        proxy_pass http://127.0.0.1:5101;
        include /etc/nginx/sites-available/snippets/proxy_common.conf;

        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # Privileged host control API (proxied to localhost-only service).
    # Maps /portal/api/admin/control/<svc>/<action> -> /control/<svc>/<action>
    location ^~ /portal/api/admin/control/ {
        auth_request /oauth2/auth;
        error_page 401 = /oauth2/sign_in;
        access_log /var/log/nginx/portal-admin-control-access.log combined;

        auth_request_set $portal_user  $upstream_http_x_auth_request_user;
        auth_request_set $portal_username $upstream_http_x_auth_request_preferred_username;
        auth_request_set $portal_roles $upstream_http_x_auth_request_groups;

        include /etc/nginx/sites-available/snippets/portal-control-token.conf;

        proxy_set_header X-Portal-User  $portal_user;
        proxy_set_header X-Portal-Username $portal_username;
        proxy_set_header X-Portal-Roles $portal_roles;
        proxy_set_header X-Control-Token $portal_control_token;
        proxy_set_header X-Request-Id $request_id;

        proxy_pass http://127.0.0.1:5120/control/;
        include /etc/nginx/sites-available/snippets/proxy_common.conf;

        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # Deterministic portal entry points. These set target cookie pre-auth so sign-in
    # returns to the intended portal instance.
    location = /portal/fnd {
        add_header Set-Cookie "portal_instance=fnd; Path=/; HttpOnly; Secure; SameSite=Lax" always;
        return 302 /portal/home;
    }


    location = /portal/tff {
        add_header Set-Cookie "portal_instance=tff; Path=/; HttpOnly; Secure; SameSite=Lax" always;
        return 302 /portal/home;
    }

    # Compatibility aliases for prior switch endpoints.
    location = /portal/switch/fnd {
        return 302 /portal/fnd;
    }

    location = /portal/switch/tff {
        return 302 /portal/tff;
    }

    # V2 shell static assets — same upstream as HTML; no OAuth on static so browsers and
    # health probes get real text/css and application/javascript (HTML shell stays protected).
    location ^~ /portal/static/ {
        auth_request off;

        proxy_set_header X-Request-Id $request_id;

        set $portal_upstream http://127.0.0.1:6101;
        if ($cookie_portal_instance = tff) {
            set $portal_upstream http://127.0.0.1:6203;
        }

        proxy_pass $portal_upstream;
        include /etc/nginx/sites-available/snippets/proxy_common.conf;

        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # protect portal routes
    location ^~ /portal {
        auth_request /oauth2/auth;
        error_page 401 = /oauth2/sign_in;

        # capture auth headers returned by oauth2-proxy auth subrequest
        auth_request_set $portal_user  $upstream_http_x_auth_request_user;
        auth_request_set $portal_username $upstream_http_x_auth_request_preferred_username;
        auth_request_set $portal_roles $upstream_http_x_auth_request_groups;

        # forward to the portal in the header names used by the platform guard
        proxy_set_header X-Portal-User  $portal_user;
        proxy_set_header X-Portal-Username $portal_username;
        proxy_set_header X-Portal-Roles $portal_roles;
        proxy_set_header X-Request-Id $request_id;

        # V2 native portal (see MyCiteV2 docs/archive/16-v2_native_portal_cutover.md)
        set $portal_upstream http://127.0.0.1:6101;
        if ($cookie_portal_instance = tff) {
            set $portal_upstream http://127.0.0.1:6203;
        }

        proxy_pass $portal_upstream;
        include /etc/nginx/sites-available/snippets/proxy_common.conf;

        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # Legacy bridge is retired for portal.*; fail closed.
    location ^~ /legacy/ {
        access_log /var/log/nginx/portal-legacy-blocked.log combined;
        return 410;
    }

    # Public boundary (e.g. /<msn_id>.json) — FND V2 portal host
    location / {
        proxy_pass http://127.0.0.1:6101;
        include /etc/nginx/sites-available/snippets/proxy_common.conf;

        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
    server_name portal.fruitfulnetworkdevelopment.com;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    return 301 https://$host$request_uri;
}
```

**Comparison (routing targets that matter):** For `/healthz`, `/portal/static/`, and `location ^~ /portal`, host effective text matches repo semantics (`6101` for FND health and portal HTML/static default; `6203` for TFF cookie branch). No drift detected in this excerpt for V2 portal + `/healthz`.

---

## 5. systemd — running unit matching intended V2 portal service

**Command:** `systemctl show mycite-v2-fnd-portal.service -p Id,ActiveState,SubState,FragmentPath,MainPID,ExecStart --no-pager`

**Output (verbatim):**

```
MainPID=48181
ExecStart={ path=/srv/venvs/fnd_portal/bin/gunicorn ; argv[]=/srv/venvs/fnd_portal/bin/gunicorn --workers 2 --bind 127.0.0.1:6101 MyCiteV2.instances._shared.portal_host.app:app ; ignore_errors=no ; start_time=[Sat 2026-04-11 00:45:09 UTC] ; stop_time=[n/a] ; pid=48181 ; code=(null) ; status=0/0 }
Id=mycite-v2-fnd-portal.service
ActiveState=active
SubState=running
FragmentPath=/etc/systemd/system/mycite-v2-fnd-portal.service
```

**Alignment:** Unit `mycite-v2-fnd-portal.service` is **active (running)**, binds **`127.0.0.1:6101`**, runs **`MyCiteV2.instances._shared.portal_host.app:app`** — matches runbook default and nginx upstream for FND V2 portal.

---

## 6. Live HTTP — `/portal/system`, static URLs, `/healthz`

### 6.1 Edge `GET https://portal.fruitfulnetworkdevelopment.com/portal/system`

**Command:** see §1 (`curl -sS -D- -o /tmp/t002_system.body ...`)

**Response headers (verbatim, first block):**

```
HTTP/1.1 200 OK
Server: nginx/1.26.3
Date: Sat, 11 Apr 2026 03:02:03 GMT
Content-Type: text/html; charset=utf-8
Transfer-Encoding: chunked
Connection: keep-alive
Cache-Control: no-cache, no-store, must-revalidate, max-age=0
Expires: Thu, 01 Jan 1970 00:00:00 UTC
Set-Cookie: _oauth2_proxy_portal=; Path=/; Expires=Sat, 11 Apr 2026 02:02:03 GMT; HttpOnly; Secure; SameSite=Lax
```

**Body sample (first lines, verbatim):**

```

<!DOCTYPE html>
<html lang="en" charset="utf-8">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <title>Sign In</title>
    <link rel="stylesheet" href="/oauth2/static/css/bulma.min.css">

    <style>
      body {
        height: 100vh;
      }
      .sign-in-box {
        max-width: 400px;
        margin: 1.25rem auto;
      }
      .logo-box {
        margin: 1.5rem 3rem;
      }
      .alert {
        padding: 5px;
        background-color: #f44336;  
        color: white;
        margin-bottom: 5px;
        border-radius: 5px
      }
       
      .closebtn {
        margin-left: 10px;
```

**Repo intent note:** Repo nginx uses `auth_request` for `location ^~ /portal`; unauthenticated clients hitting edge `/portal/system` receive **oauth2-proxy sign-in HTML** (HTTP 200). That is **consistent** with repo intent, not a live contradiction.

**Suggested grep on edge body (no matches — verbatim):**

```
=== suggested verifier grep on edge /portal/system (may be oauth) ===

```

### 6.2 Loopback `GET http://127.0.0.1:6101/portal/system` (shell markers)

**Command:** `curl -sS --max-time 25 'http://127.0.0.1:6101/portal/system' | grep -n 'shell-template: v2-composition\|build:' | head -n 20`

**Output (verbatim):**

```
44:  <!-- shell-template: v2-composition build=06b0b6c-static-route-20260411 -->
97:          <div class="ide-sessionLine ide-sessionLine--dim">build: 06b0b6c-static-route-20260411</div>
```

### 6.3 `HEAD` static assets

**`curl -I` `.../portal/static/portal.css` (verbatim):**

```
HTTP/1.1 200 OK
Server: nginx/1.26.3
Date: Sat, 11 Apr 2026 03:02:04 GMT
Content-Type: text/css; charset=utf-8
Content-Length: 124104
Connection: keep-alive
Content-Disposition: inline; filename=portal.css
Last-Modified: Fri, 10 Apr 2026 23:03:07 GMT
Cache-Control: no-cache
ETag: "1775862187.48-124104-2275810763"
Accept-Ranges: bytes
```

**`curl -I` `.../portal/static/v2_portal_shell.js` (verbatim):**

```
HTTP/1.1 200 OK
Server: nginx/1.26.3
Date: Sat, 11 Apr 2026 03:02:04 GMT
Content-Type: text/javascript; charset=utf-8
Content-Length: 19220
Connection: keep-alive
Content-Disposition: inline; filename=v2_portal_shell.js
Last-Modified: Fri, 10 Apr 2026 23:03:02 GMT
Cache-Control: no-cache
ETag: "1775862182.884-19220-2192908509"
Accept-Ranges: bytes
```

### 6.4 `GET /healthz`

**Headers + start of body (verbatim, one `curl -D-` stream; body truncated after first line in tool capture):**

```
HTTP/1.1 200 OK
Server: nginx/1.26.3
Date: Sat, 11 Apr 2026 03:02:04 GMT
Content-Type: application/json
Content-Length: 2909
Connection: keep-alive

{"analytics_root":{"analytics_root":"/srv/webapps/clients/fruitfulnetworkdevelopment.com/analytics","domain":"fruitfulnetworkdevelopment.com","events_file":"/srv/webapps/clients/fruitfulnetworkdevelopment.com/analytics/events/2026-04.ndjson","legacy_events_file":"/srv/webapps/fruitfulnetworkdevelopment.com/analytics/events/2026-04.ndjson","warnings":[],"year_month":"2026-04"},"aws_config_health":{"audit_storage_file_configured":true,"configured":true,"exists":true,"live_profile_mapping":true,"status_file":"/srv/mycite-state/instances/fnd/private/utilities/tools/aws-csm/aws-csm.fnd.dylan.json"},"datum_health":{"materialization_status":{"canonical_source":"loaded","legacy_root_conflict_count":0,"legacy_root_fallback":"blocked","payload_cache_count":8,"system_source_count":3},"ok":true,"row_count":56,"source_files":{"anthology":"/srv/mycite-state/instances/fnd/data/system/anthology.json","ignored_legacy_root_files":[],"legacy_root_candidates":["/srv/mycite-state/instances/fnd/data/anthology.json","/srv/mycite-state/instances/fnd/data/samras-msn.json","/srv/mycite-state/instances/fnd/data/samras-txa.json"],"payload_cache":["/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json","/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.msn-address_nodes.json","/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json","/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.msn-legal_entity.json","/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.msn-natural_entity.json","/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.quadrennium_cycle.json","/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.registrar.json","/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.txa.json"],"system_sources":["/srv/mycite-state/instances/fnd/data/system/sources/sc.3-2-3-17-77-1-6-4-1-4.msn-legal_entity.json","/srv/mycite-state/instances/fnd/data/system/sources/sc.3-2-3-17-77-1-6-4-1-4.msn-natural_entity.json","/srv/mycite-state/instances/fnd/data/system/sources/sc.3-2-3-17-77-1-6-4-1-4.quadrennium_cycle.json"]},"warnings":[]},"host_shape":"v2_native","ok":true,"portal_static_bundle":{"package_static_dir":"/srv/repo/mycite-core/MyCiteV2/instances/_shared/portal_host/static","portal_css_present":true,"portal_css_size_bytes":124104,"static_ok":true,"static_url_path":"/portal/static","v2_portal_shell_js_present":true},"schema":"mycite.v2.portal.health.v1","state_roots":{"analytics_domain":"fruitfulnetworkdevelopment.com","analytics_webapps_root":"/srv/webapps","data_dir":"/srv/mycite-state/instances/fnd/data","private_dir":"/srv/mycite-state/instances/fnd/private","public_dir":"/srv/mycite-state/instances/fnd/public","tenant_id":"fnd"},"tenant_id":"fnd"}
```

**Formatted body (`python3 -m json.tool`, verbatim):**

```json
{
    "analytics_root": {
        "analytics_root": "/srv/webapps/clients/fruitfulnetworkdevelopment.com/analytics",
        "domain": "fruitfulnetworkdevelopment.com",
        "events_file": "/srv/webapps/clients/fruitfulnetworkdevelopment.com/analytics/events/2026-04.ndjson",
        "legacy_events_file": "/srv/webapps/fruitfulnetworkdevelopment.com/analytics/events/2026-04.ndjson",
        "warnings": [],
        "year_month": "2026-04"
    },
    "aws_config_health": {
        "audit_storage_file_configured": true,
        "configured": true,
        "exists": true,
        "live_profile_mapping": true,
        "status_file": "/srv/mycite-state/instances/fnd/private/utilities/tools/aws-csm/aws-csm.fnd.dylan.json"
    },
    "datum_health": {
        "materialization_status": {
            "canonical_source": "loaded",
            "legacy_root_conflict_count": 0,
            "legacy_root_fallback": "blocked",
            "payload_cache_count": 8,
            "system_source_count": 3
        },
        "ok": true,
        "row_count": 56,
        "source_files": {
            "anthology": "/srv/mycite-state/instances/fnd/data/system/anthology.json",
            "ignored_legacy_root_files": [],
            "legacy_root_candidates": [
                "/srv/mycite-state/instances/fnd/data/anthology.json",
                "/srv/mycite-state/instances/fnd/data/samras-msn.json",
                "/srv/mycite-state/instances/fnd/data/samras-txa.json"
            ],
            "payload_cache": [
                "/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json",
                "/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.msn-address_nodes.json",
                "/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json",
                "/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.msn-legal_entity.json",
                "/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.msn-natural_entity.json",
                "/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.quadrennium_cycle.json",
                "/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.registrar.json",
                "/srv/mycite-state/instances/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.txa.json"
            ],
            "system_sources": [
                "/srv/mycite-state/instances/fnd/data/system/sources/sc.3-2-3-17-77-1-6-4-1-4.msn-legal_entity.json",
                "/srv/mycite-state/instances/fnd/data/system/sources/sc.3-2-3-17-77-1-6-4-1-4.msn-natural_entity.json",
                "/srv/mycite-state/instances/fnd/data/system/sources/sc.3-2-3-17-77-1-6-4-1-4.quadrennium_cycle.json"
            ]
        },
        "warnings": []
    },
    "host_shape": "v2_native",
    "ok": true,
    "portal_static_bundle": {
        "package_static_dir": "/srv/repo/mycite-core/MyCiteV2/instances/_shared/portal_host/static",
        "portal_css_present": true,
        "portal_css_size_bytes": 124104,
        "static_ok": true,
        "static_url_path": "/portal/static",
        "v2_portal_shell_js_present": true
    },
    "schema": "mycite.v2.portal.health.v1",
    "state_roots": {
        "analytics_domain": "fruitfulnetworkdevelopment.com",
        "analytics_webapps_root": "/srv/webapps",
        "data_dir": "/srv/mycite-state/instances/fnd/data",
        "private_dir": "/srv/mycite-state/instances/fnd/private",
        "public_dir": "/srv/mycite-state/instances/fnd/public",
        "tenant_id": "fnd"
    },
    "tenant_id": "fnd"
}
```

**Live vs repo intent:** HTTP 200, `schema` **`mycite.v2.portal.health.v1`**, **`host_shape`** **`v2_native`**, **`static_url_path`** **`/portal/static`**, **`ok`:** **`true`**, static bundle reports CSS/JS present — **aligned** with native V2 portal host expectations documented in the runbook.

---

## 7. Live evidence (summary pointer)

- **Deploy-truth transcript:** §2.  
- **Nginx host vs repo:** §4.  
- **systemd:** §5 (and §2 `systemctl status`).  
- **HTTP:** §6.

---

## 8. Mismatches (repo / host / live)

**None found** for the scoped checks above:

- Host **effective** nginx routing for `/healthz`, `/portal/static/`, and `location ^~ /portal` matches **`srv-infra`** repo file content in this workspace.  
- **Edge** `/portal/system` without session returns **OAuth sign-in** HTML; **repo nginx** explicitly protects `location ^~ /portal` with `auth_request` — this is **expected**, not a mismatch.  
- **V2 shell HTML markers** verified on **loopback `127.0.0.1:6101`**, matching operational model in `reports/T-002-operator-runbook.md`.

**Caveat (non-blocking for this verdict):** Failure-path behavior of `verify_v2_portal_deploy_truth.sh` (non-zero exits) was not validated by deliberate fault injection on production.

---

## 9. Final verdict

**pass**

---

## 10. Recommended task status

Per `tasks/T-002-deploy-truth-automation.yaml` `closure_rule` and this **pass** verdict: lead may mark T-002 **`complete`** (or equivalent closed state your tracker uses), with `primary_type` updated from **`verification_pending`** once the lead records closure. Until the lead updates YAML, suggest **`status: complete`** and note verifier evidence file: `reports/T-002-verification.md`.
