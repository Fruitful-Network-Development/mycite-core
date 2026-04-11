# Verification report

**Task:** T-005 — Unify repo routing truth with live host routing truth  
**Role:** verifier  
**Date:** 2026-04-11

**Task type:** `repo_and_deploy`

---

## 1. Repo layer

Inspected **`/srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`**. Grep output (task **`execution.repo_test_command`**) shows **`location = /healthz`** → `127.0.0.1:6101`, **`location ^~ /portal/static/`** with **`auth_request off`** and **`$portal_upstream`** `6101` / `6203` cookie branch, and **`location ^~ /portal`** with the same upstream pattern — consistent with intended V2 routing for **`/portal`**, **`/portal/static/*`**, and **`/healthz`**.

Checked-in snapshot artifact **`reports/T-005-host-nginx-snapshot.conf`** is byte-identical to the live host file (see host layer **`diff`**).

---

## 2. Host layer

### 2.1 Commands used

```text
cd /srv/repo/srv-infra && grep -n "location \^~ /portal/static/\|location \^~ /portal \|set \$portal_upstream\|healthz" nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf
```

```text
diff /etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf /srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf; echo "diff_exit=$?"
```

```text
sha256sum /etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf /srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf
```

```text
diff /etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf /srv/repo/mycite-core/reports/T-005-host-nginx-snapshot.conf; echo "snapshot_diff_exit=$?"
```

```text
sudo -n /usr/sbin/nginx -t 2>&1; echo "nginx_t_exit=$?"
```

```text
sudo -n systemctl reload nginx 2>&1; echo "reload_exit=$?"
```

### 2.2 Captured stdout/stderr

**Repo grep (`repo_test_command`):**

```text
42:    # keep healthz public (no auth). Intentionally targets V2 native FND portal (6101), not legacy 5101.
43:    location = /healthz {
45:        proxy_pass http://127.0.0.1:6101/healthz;
97:    # AWS admin APIs — legacy path still routed to V1-era fnd_portal (5101). Canonical V2 AWS tools use /portal/api/v2/admin/aws/* via location ^~ /portal below (6101/6203).
169:    location ^~ /portal/static/ {
174:        set $portal_upstream http://127.0.0.1:6101;
176:            set $portal_upstream http://127.0.0.1:6203;
187:    location ^~ /portal {
203:        set $portal_upstream http://127.0.0.1:6101;
205:            set $portal_upstream http://127.0.0.1:6203;
```

**Host vs repo:**

```text
diff_exit=0
```

```text
4ef66bfe4025dff42afd10733b1d5dd7dd7aeeb8cdd9d52c71941e85dd0bef35  /etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf
4ef66bfe4025dff42afd10733b1d5dd7dd7aeeb8cdd9d52c71941e85dd0bef35  /srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf
```

**Host vs committed snapshot artifact:**

```text
snapshot_diff_exit=0
```

**`nginx -t`:**

```text
2026/04/11 04:12:49 [warn] 94394#94394: could not build optimal proxy_headers_hash, you should increase either proxy_headers_hash_max_size: 512 or proxy_headers_hash_bucket_size: 64; ignoring proxy_headers_hash_bucket_size
2026/04/11 04:12:49 [warn] 94394#94394: could not build optimal proxy_headers_hash, you should increase either proxy_headers_hash_max_size: 512 or proxy_headers_hash_bucket_size: 64; ignoring proxy_headers_hash_bucket_size
2026/04/11 04:12:49 [warn] 94394#94394: could not build optimal proxy_headers_hash, you should increase either proxy_headers_hash_max_size: 512 or proxy_headers_hash_bucket_size: 64; ignoring proxy_headers_hash_bucket_size
2026/04/11 04:12:49 [warn] 94394#94394: could not build optimal proxy_headers_hash, you should increase either proxy_headers_hash_max_size: 512 or proxy_headers_hash_bucket_size: 64; ignoring proxy_headers_hash_bucket_size
2026/04/11 04:12:49 [warn] 94394#94394: could not build optimal proxy_headers_hash, you should increase either proxy_headers_hash_max_size: 512 or proxy_headers_hash_bucket_size: 64; ignoring proxy_headers_hash_bucket_size
2026/04/11 04:12:49 [warn] 94394#94394: could not build optimal proxy_headers_hash, you should increase either proxy_headers_hash_max_size: 512 or proxy_headers_hash_bucket_size: 64; ignoring proxy_headers_hash_bucket_size
2026/04/11 04:12:49 [warn] 94394#94394: could not build optimal proxy_headers_hash, you should increase either proxy_headers_hash_max_size: 512 or proxy_headers_hash_bucket_size: 64; ignoring proxy_headers_hash_bucket_size
2026/04/11 04:12:49 [warn] 94394#94394: could not build optimal proxy_headers_hash, you should increase either proxy_headers_hash_max_size: 512 or proxy_headers_hash_bucket_size: 64; ignoring proxy_headers_hash_bucket_size
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
nginx_t_exit=0
```

**Reload (verifier-run, before live re-check):**

```text
reload_exit=0
```

---

## 3. Live HTTP / operational layer

### 3.1 Task `execution.live_check_command` (verbatim)

Command:

```text
cd /tmp &&
curl -I https://portal.fruitfulnetworkdevelopment.com/portal/static/portal.css &&
curl -I https://portal.fruitfulnetworkdevelopment.com/portal/static/v2_portal_shell.js &&
curl -I https://portal.fruitfulnetworkdevelopment.com/portal/system &&
curl -s https://portal.fruitfulnetworkdevelopment.com/healthz | python3 -m json.tool
```

Output (single shell invocation; curl progress meters included):

```text
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed

  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
  0  121k    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
HTTP/1.1 200 OK
Server: nginx/1.26.3
Date: Sat, 11 Apr 2026 04:13:48 GMT
Content-Type: text/css; charset=utf-8
Content-Length: 124104
Connection: keep-alive
Content-Disposition: inline; filename=portal.css
Last-Modified: Fri, 10 Apr 2026 23:03:07 GMT
Cache-Control: no-cache
ETag: "1775862187.48-124104-2275810763"
Accept-Ranges: bytes

  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed

  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
  0 19220    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
HTTP/1.1 200 OK
Server: nginx/1.26.3
Date: Sat, 11 Apr 2026 04:13:48 GMT
Content-Type: text/javascript; charset=utf-8
Content-Length: 19220
Connection: keep-alive
Content-Disposition: inline; filename=v2_portal_shell.js
Last-Modified: Fri, 10 Apr 2026 23:03:02 GMT
Cache-Control: no-cache
ETag: "1775862182.884-19220-2192908509"
Accept-Ranges: bytes

  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed

  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
HTTP/1.1 200 OK
Server: nginx/1.26.3
Date: Sat, 11 Apr 2026 04:13:48 GMT
Content-Type: text/html; charset=utf-8
Connection: keep-alive
Cache-Control: no-cache, no-store, must-revalidate, max-age=0
Expires: Thu, 01 Jan 1970 00:00:00 UTC
Set-Cookie: _oauth2_proxy_portal=; Path=/; Expires=Sat, 11 Apr 2026 03:13:48 GMT; HttpOnly; Secure; SameSite=Lax

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

**Post-reload spot check** (`sudo -n systemctl reload nginx` then **`curl -I .../healthz`**, first 8 header lines):

```text
HTTP/1.1 200 OK
Server: nginx/1.26.3
Date: Sat, 11 Apr 2026 04:12:56 GMT
Content-Type: application/json
Content-Length: 2909
Connection: keep-alive
```

### 3.2 Canonical deploy-truth script (independent rerun)

Command:

```text
cd /srv/repo/mycite-core && bash scripts/verify_v2_portal_deploy_truth.sh
```

Output:

```text
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
     Active: active (running) since Sat 2026-04-11 00:45:09 UTC; 3h 27min ago
 Invocation: c589398e81a54203b3935e49b8120179
   Main PID: 48181 (gunicorn)
      Tasks: 4 (limit: 1126)
     Memory: 28.6M (peak: 58.4M, swap: 42.1M, swap peak: 42.3M)
        CPU: 2.156s
     CGroup: /system.slice/mycite-v2-fnd-portal.service
             ├─48181 /srv/venvs/fnd_portal/bin/python3 /srv/venvs/fnd_portal/bin/gunicorn --workers 2 --bind 127.0.0.1:6101 MyCiteV2.instances._shared.portal_host.app:app
             ├─48184 /srv/venvs/fnd_portal/bin/python3 /srv/venvs/fnd_portal/bin/gunicorn --workers 2 --bind 127.0.0.1:6101 MyCiteV2.instances._shared.portal_host.app:app
             └─48186 /srv/venvs/fnd_portal/bin/python3 /srv/venvs/fnd_portal/bin/gunicorn --workers 2 --bind 127.0.0.1:6101 MyCiteV2.instances._shared.portal_host.app:app

Apr 11 00:45:09 ip-172-31-21-63 systemd[1]: Started mycite-v2-fnd-portal.service - MyCite V2 Fruitful Network Development portal.
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48181]: [2026-04-11 00:45:09 +0000] [48181] [INFO] Starting gunicorn 25.3.0
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48181]: [2026-04-11 00:45:09 +0000] [48181] [INFO] Listening at: http://127.0.0.1:6101 (48181)
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48181]: [2026-04-11 00:45:09 +0000] [48181] [INFO] Using worker: sync
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48184]: [2026-04-11 00:45:09 +0000] [48184] [INFO] Booting worker with pid 48184
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48186]: [2026-04-11 00:45:09 +0000] [48186] [INFO] Booting worker with pid 48186
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48181]: [2026-04-11 00:45:09 +0000] [48181] [INFO] Control socket listening at /home/admin/.gunicorn/gunicorn.ctl
systemd ActiveState=active SubState=running FragmentPath=/etc/systemd/system/mycite-v2-fnd-portal.service
systemd: OK
== on-host: nginx effective config (semantic grep vs repo intent) ==
nginx effective vs intent (grep-level): OK

All deploy-truth checks passed.
```

---

## 4. Acceptance mapping

| Acceptance criterion | Evidence | Result |
|----------------------|-----------|--------|
| Repo nginx reflects intended V2 routing for `/portal` and `/portal/static` if used | §2.2 repo grep; config blocks `location ^~ /portal/static/` and `location ^~ /portal` with `6101`/`6203` | pass |
| Actual host nginx inspected and captured in reports | §2.2 `diff_exit=0`, `snapshot_diff_exit=0`; artifact `reports/T-005-host-nginx-snapshot.conf` | pass |
| Routing mismatch fixed or documented | No mismatch (`diff`/`sha256` identical) | pass |
| Live HTTP after reload matches checked-in intent | §2.2 reload `exit=0`; §3.1 `200` static + JSON `healthz`; §3.2 deploy-truth `exit 0` | pass |
| Verifier confirms repo, host, live agree | §2–3 independent commands | pass |

---

## 5. Repo / host / live mismatches

None. **`proxy_headers_hash`** warnings from **`nginx -t`** are advisory; syntax test succeeded.

Edge **`/portal/system`** returns **200** HTML that is not the V2 shell body without session (**OAuth**), while **`verify_v2_portal_deploy_truth.sh`** confirms V2 markers via **loopback** `127.0.0.1:6101` — consistent with nginx **`auth_request`** on **`location ^~ /portal`** and **`auth_request off`** on static and **`/healthz`**.

---

## 6. Final verdict

**Verdict (required):** `PASS`

Repo intent file, on-host **`sites-available`** file, committed snapshot, and live HTTPS checks (after verifier **`nginx` reload**) align; deploy-truth script passes independently.

---

## 7. Recommended next status

`status: verified_pass`  
`verification_result: pass`  
`execution.current_role: lead`  
`execution.next_role: lead`  

Lead may set **`resolved`** per **`closure_rule`** when satisfied.
