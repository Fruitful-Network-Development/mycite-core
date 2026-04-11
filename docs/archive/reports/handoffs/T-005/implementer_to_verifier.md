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
