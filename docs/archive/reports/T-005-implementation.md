# T-005 implementation report

**Task:** T-005 — Unify repo routing truth with live host routing truth  
**Role:** implementer  
**Date:** 2026-04-11

---

## 1. Files changed

| Path | Change type |
|------|-------------|
| `reports/T-005-host-nginx-snapshot.conf` | diagnostic (verbatim host snapshot) |
| `scripts/verify_v2_portal_deploy_truth.sh` | diagnostic |
| `reports/T-005-implementation.md` | documentation |
| `reports/handoffs/T-005/implementer_to_verifier.md` | documentation |

**No changes** to `srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`, `app.py`, or `portal.html`: inspected host file and repo intent file are **byte-identical** (see §3).

---

## 2. Why each file changed

- **`reports/T-005-host-nginx-snapshot.conf`:** Task artifact `artifacts.host_config_snapshot` — verbatim copy of **`/etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`** as loaded for `portal.fruitfulnetworkdevelopment.com` (also referenced from `sites-enabled/`).
- **`scripts/verify_v2_portal_deploy_truth.sh`:** Resolve nginx as **`PATH` → `/usr/sbin/nginx`** (optional **`NGINX_BIN`** override) so `nginx -T` host checks work when `nginx` is not on a non-root `PATH`; use **`sudo -n "$ngx" -T`** for predictable non-interactive sudo.
- **Reports / handoff:** Role outputs per `tasks/README.md`.

---

## 3. Commands run

### 3.1 Repo routing sanity (`execution.repo_test_command`)

```text
$ cd /srv/repo/mycite-core && grep -n "location \^~ /portal/static/\|location \^~ /portal \|set \$portal_upstream\|healthz" /srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf
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

### 3.2 Host file vs repo intent (diff + checksum)

**Host path:** `/etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`  
**Repo path:** `/srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`

```text
$ diff /etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf /srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf; echo "diff_exit=$?"
diff_exit=0

$ sha256sum /etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf /srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf
4ef66bfe4025dff42afd10733b1d5dd7dd7aeeb8cdd9d52c71941e85dd0bef35  /etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf
4ef66bfe4025dff42afd10733b1d5dd7dd7aeeb8cdd9d52c71941e85dd0bef35  /srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf
```

### 3.3 `nginx -t` (syntax test)

```text
$ sudo -n /usr/sbin/nginx -t 2>&1
2026/04/11 04:11:44 [warn] ... proxy_headers_hash ...
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### 3.4 Nginx reload

```text
$ sudo -n systemctl reload nginx 2>&1; echo exit=$?
exit=0
```

### 3.5 Deploy-truth script (end-to-end)

```text
$ cd /srv/repo/mycite-core && bash scripts/verify_v2_portal_deploy_truth.sh
== repo: portal.html markers ==
...
All deploy-truth checks passed.
```

(Full transcript is long; key lines include **live static + healthz: OK**, **portal HTML markers: OK** via loopback `http://127.0.0.1:6101/portal/system` after edge `/portal/system` returned non-shell HTML without session, **nginx effective vs intent (grep-level): OK**.)

### 3.6 Live HTTP checks (separate routes)

**`/portal/static/portal.css`**

```text
$ curl -sS -I --max-time 25 https://portal.fruitfulnetworkdevelopment.com/portal/static/portal.css | head -12
HTTP/1.1 200 OK
Server: nginx/1.26.3
Content-Type: text/css; charset=utf-8
...
```

**`/portal/static/v2_portal_shell.js`**

```text
$ curl -sS -I --max-time 25 https://portal.fruitfulnetworkdevelopment.com/portal/static/v2_portal_shell.js | head -12
HTTP/1.1 200 OK
Server: nginx/1.26.3
Content-Type: text/javascript; charset=utf-8
...
```

**`/portal` and `/portal/system` (edge, unauthenticated)**

```text
$ curl -sS -I --max-time 25 https://portal.fruitfulnetworkdevelopment.com/portal | head -12
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Set-Cookie: _oauth2_proxy_portal=; Path=/; Expires=...
```

```text
$ curl -sS -I --max-time 25 https://portal.fruitfulnetworkdevelopment.com/portal/system | head -12
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Set-Cookie: _oauth2_proxy_portal=; Path=/; Expires=...
```

**Interpretation:** Edge responses are consistent with **OAuth-wrapped** portal routes (HTML shell markers verified on **loopback** `127.0.0.1:6101` by `verify_v2_portal_deploy_truth.sh`). Static and `/healthz` are served **without** auth per nginx `location` blocks.

**`/healthz`**

```text
$ curl -sS -I --max-time 25 https://portal.fruitfulnetworkdevelopment.com/healthz | head -12
HTTP/1.1 200 OK
Server: nginx/1.26.3
Content-Type: application/json
...
```

```text
$ curl -sS --max-time 25 https://portal.fruitfulnetworkdevelopment.com/healthz | python3 -m json.tool | head -25
{
    "analytics_root": {
        "analytics_root": "/srv/webapps/clients/fruitfulnetworkdevelopment.com/analytics",
        ...
    },
    ...
}
```

---

## 4. Tests run

- **`execution.repo_test_command`:** run — see §3.1.
- **`bash scripts/verify_v2_portal_deploy_truth.sh`:** exit **0** — see §3.5.

---

## 5. Deploy actions taken

- Ran **`sudo -n /usr/sbin/nginx -t`** (successful).
- Ran **`sudo -n systemctl reload nginx`** (exit 0).
- Captured host site config into **`reports/T-005-host-nginx-snapshot.conf`** from **`/etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`**.

---

## 6. What still requires independent verification

Per **`closure_rule`**, the **verifier** must independently:

1. Inspect **repo** nginx (`srv-infra`) and confirm V2 routing intent for **`/portal`**, **`/portal/static/`**, and **`/healthz`**.
2. Re-read **on-host** nginx (path may differ on other hosts; here **`/etc/nginx/sites-available/...`**) and compare to repo / snapshot.
3. Re-run **live** `curl` (or equivalent) and **`verify_v2_portal_deploy_truth.sh`** with **verbatim** transcripts in **`reports/T-005-verification.md`**.
4. Issue **pass** or **fail**; the implementer does **not** certify “routing unified” for lead closure.

---

## 7. Recommended next status

- `status: verification_pending`
- `execution.current_role: verifier`
- `execution.next_role: lead`
- `verification_result: pending` until the verifier completes
