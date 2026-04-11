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

server {
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

server {
    listen 80;
    server_name portal.fruitfulnetworkdevelopment.com;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    return 301 https://$host$request_uri;
}

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

# Lead → Implementer: T-005 routing truth unification

## Task classification

- **primary_type:** `repo_and_deploy` (confirmed). Acceptance requires **repo nginx intent**, **on-host nginx reality**, and **live HTTP** to align; closure is **not** repo-only.
- **Evidence for closure:** Per `closure_rule` and `agent/constraints.md` §5 / §88: implementer produces `reports/T-005-implementation.md`, `reports/T-005-host-nginx-snapshot.conf`, and `reports/handoffs/T-005/implementer_to_verifier.md` with **separate** repo vs host vs live sections and **verbatim** command output where applicable. **Verifier** must independently confirm agreement in `reports/T-005-verification.md` with **verbatim** transcripts for host inspection and live `curl` (or equivalent); implementer narrative does **not** substitute for verifier evidence.

## Repo roots (scope spans two repos)

Paths in the task YAML are relative to the owning repo:

| Repo | Root (typical workspace) |
|------|---------------------------|
| **srv-infra** | `srv-infra/` — nginx: `nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf` |
| **mycite-core** | `mycite-core/` — portal host: `MyCiteV2/instances/_shared/portal_host/app.py`, `.../templates/portal.html`, `scripts/verify_v2_portal_deploy_truth.sh` |

## Exact files to read (in order)

1. `tasks/T-005-routing-truth-unification.yaml` — acceptance, `artifacts.host_config_snapshot`, `execution.repo_test_command`, `execution.live_check_command`.
2. `MyCiteV2/docs/ontology/structural_invariants.md` and `MyCiteV2/docs/plans/authority_stack.md` — task authority; **structural_invariants**: hosts compose modules; **no** treating a runtime route as domain truth beyond what this task needs for nginx ↔ app alignment.
3. `MyCiteV2/docs/audits/v2_shell_visual_parity_and_standards_audit_2026-04-10.md` — audit context only; **current repo + host + live** override stale narration.
4. **srv-infra:** `nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf` — full file; focus `location` blocks for `/healthz`, `/portal/static/`, `^~ /portal`, and any upstream variables affecting V2 (6101 vs legacy).
5. **mycite-core:** `MyCiteV2/instances/_shared/portal_host/app.py`, `MyCiteV2/instances/_shared/portal_host/templates/portal.html` — how the app expects `/portal`, static, and health to be exposed behind nginx.
6. **mycite-core:** `scripts/verify_v2_portal_deploy_truth.sh` — reuse or extend if it already encodes deploy checks; do not invent a second divergent truth source without documenting why.

## Exact goal

1. **Checked-in nginx** (`srv-infra`) reflects **intended** V2 routing for `/portal` and explicit `/portal/static/` handling (and `/healthz`) per acceptance.
2. **Host truth:** Inspect the **actual** enabled nginx config for `portal.fruitfulnetworkdevelopment.com` on the deployment host; capture a verbatim snapshot into **`reports/T-005-host-nginx-snapshot.conf`** (task `artifacts.host_config_snapshot`). If host path differs from repo path, document the real path and how it maps to the repo file.
3. **Reload / validate:** Capture **`nginx -t`** and **reload** (or equivalent approved reload) output on the host per `implementation_requirements`.
4. **Live checks:** After reload, confirm live HTTP matches intent. Treat **`/portal`**, **`/portal/static/*`**, and **`/healthz`** as **separate** checks (task acceptance). Use or extend `execution.live_check_command` as a baseline; paste **full** `curl -I` / body evidence in the implementation report (redact secrets only).
5. **Drift:** Any mismatch between repo, host snapshot, and live behavior is **fixed** in repo and/or host as allowed by access, or **explicitly documented as a blocker** with no silent partial closure.

## Constraints that matter

- **Repo / deploy / live separation** (`agent/constraints.md` §4, §7): keep implementation report sections **Repo findings**, **Deploy / host findings**, **Live verification** clearly separated; do not merge layers in one paragraph.
- **Verifier independence:** Implementer does not issue final “routing unified” verdict; verifier re-runs inspection and live checks.
- **Fail-closed:** If host access is impossible, set task **`blocked`** with an honest reason in `reports/T-005-implementation.md` and the implementer handoff — do not claim unification without host evidence.

## Required outputs

1. **Repo edits** as needed: primarily `srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`; portal host files only if required to align documented or actual behavior with nginx (stay within task scope).
2. **`reports/T-005-host-nginx-snapshot.conf`** — host config snapshot (verbatim content from the inspected host file(s), or clear statement if blocked).
3. **`reports/T-005-implementation.md`** — per `tasks/README.md` §9; must include **commands run**, **tests/deploy**, **host inspection**, **live verification**, gaps, recommended `verification_pending`.
4. **`reports/handoffs/T-005/implementer_to_verifier.md`** — per §8: what changed, commands run, what verifier must re-run independently, risks.
5. **Task YAML (implementer):** when handing off, set `status` to **`verification_pending`**, `execution.current_role` to **`verifier`**, `execution.next_role` to **`lead`**. Do **not** set `verification_result` or `resolved`.

## Stop conditions

- **Blocked:** No SSH/sudo/host access to read nginx and reload — document and set `blocked` with `execution` fields per implementer role rules.
- **Blocked:** Live URL unreachable from verifier environment — document; do not fake curl output.
- Do not close from “config looks right in the editor” without host file match and live checks after any reload.

## Recommended next task status after implementation

- `status: verification_pending`
- `execution.current_role: verifier`
- `execution.next_role: lead`
- `verification_result: pending` until verifier completes

# Implementer → Verifier: T-005

## Files changed

- `reports/T-005-host-nginx-snapshot.conf` — verbatim copy from **`/etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`** on this host (2026-04-11).
- `scripts/verify_v2_portal_deploy_truth.sh` — resolve nginx binary via **`PATH` → `/usr/sbin/nginx`** or **`NGINX_BIN`**; **`sudo -n "$ngx" -T`** for dumps.

## Commands run

- Task **`execution.repo_test_command`** (grep over repo nginx file).
- **`diff`** + **`sha256sum`** between host **`/etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`** and **`/srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`** — **identical** (`diff_exit=0`, matching hashes).
- **`sudo -n /usr/sbin/nginx -t`**, **`sudo -n systemctl reload nginx`**.
- **`cd /srv/repo/mycite-core && bash scripts/verify_v2_portal_deploy_truth.sh`** — **exit 0**.
- Live **`curl -I`** / **`curl`** for **`/portal/static/*`**, **`/portal`**, **`/portal/system`**, **`/healthz`** — see **`reports/T-005-implementation.md`**.

## Reports written

- `reports/T-005-implementation.md`
- `reports/T-005-host-nginx-snapshot.conf`

## Unresolved risks

- Edge **`/portal`** and **`/portal/system`** return **200** with **OAuth / sign-in** HTML when unauthenticated; V2 shell HTML was validated via **loopback** in the deploy-truth script. Verifier should confirm this matches expected security posture and acceptance.

## What must be independently verified

1. Repo **`srv-infra`** nginx file matches **your** host inspection (not only this implementer’s snapshot).
2. **`nginx -T`** semantics still include **`location = /healthz`**, **`location ^~ /portal/static/`**, **`location ^~ /portal`**, and **6101/6203** upstream intent.
3. Live HTTPS checks for **static**, **healthz**, and **portal** routes after any changes you make.
4. Run **`bash scripts/verify_v2_portal_deploy_truth.sh`** from **`mycite-core`** and capture **verbatim** output in **`reports/T-005-verification.md`**.

## Recommended next task status

`verification_pending` → verifier issues **`verified_pass`** or **`verified_fail`** and updates **`verification_result`**; lead handles **`resolved`** per **`closure_rule`**.

# Verifier → Lead: T-005

## Verification commands used

1. **`execution.repo_test_command`** — `grep` over `srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf` (verbatim output in `reports/T-005-verification.md` §2.2).
2. **Host vs repo** — `diff` and `sha256sum` between `/etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf` and `/srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf` — identical (`diff_exit=0`, matching hashes).
3. **Host vs snapshot artifact** — `diff` host file to `reports/T-005-host-nginx-snapshot.conf` — `snapshot_diff_exit=0`.
4. **`sudo -n /usr/sbin/nginx -t`** — syntax OK (`nginx_t_exit=0`); proxy hash warnings only.
5. **`sudo -n systemctl reload nginx`** — `reload_exit=0` (verifier-executed before live re-check).
6. **`execution.live_check_command`** — four-part `curl` chain to static URLs, `/portal/system`, and `healthz` + `json.tool` (full transcript in verification report §3.1).
7. **`cd /srv/repo/mycite-core && bash scripts/verify_v2_portal_deploy_truth.sh`** — exit **0**; full stdout in verification report §3.2.

## Evidence summary

- **Repo / host:** On-host portal vhost file matches checked-in **`srv-infra`** file and **`T-005-host-nginx-snapshot.conf`** byte-for-byte on this host.
- **Live:** Static assets and **`/healthz`** return **200** with expected content types; **`/portal/system`** at edge is **200** HTML behind OAuth (expected); deploy-truth script validates V2 shell markers via **loopback** and reports **All deploy-truth checks passed.**

## Verdict

**PASS**

## Mismatches

None.

## Recommended final status

- `status: verified_pass`, `verification_result: pass`, `execution.current_role: lead`, `execution.next_role: lead`
- Lead may set `status: resolved` per task `closure_rule` after reading `reports/T-005-verification.md`.
