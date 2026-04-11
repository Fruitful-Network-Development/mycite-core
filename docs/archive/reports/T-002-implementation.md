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
