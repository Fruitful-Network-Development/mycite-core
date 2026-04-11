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
