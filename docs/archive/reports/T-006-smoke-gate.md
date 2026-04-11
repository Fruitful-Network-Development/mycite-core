# T-006 — Portal operational smoke gate (repo + live)

**Purpose:** Repeatable regression gate for the V2 native portal shell. **Repo tests first**, then **live / host deploy-truth** checks. Either step failing is enough to **block** task closure for any work that depends on this gate.

**Canonical commands** are defined in **`tasks/T-006-operational-smoke-and-regression-gates.yaml`** under `execution.repo_test_command` and `execution.live_check_command`. **Keep this document and that YAML in lockstep** if commands change.

**Evidence:** Implementer records a run in **`reports/T-006-implementation.md`**; verifier records an **independent** run in **`reports/T-006-verification.md`** using the templates under **`reports/templates/`** (separate repo / host / live sections where applicable).

**Layering:** This gate **adds** smoke and deploy-truth on top of existing **unittest** and **integration** suites (`MyCiteV2/tests/integration/test_v2_native_portal_host.py`, architecture boundaries, etc.). It **does not** replace them.

---

## Prerequisites

- **Repo root:** `mycite-core` checkout (this document assumes **`/srv/repo/mycite-core`** as in the task commands).
- **Python:** `PYTHONPATH` must include the `mycite-core` root (as in Step 1).
- **Interpreter:** Task default is **`/srv/venvs/fnd_portal/bin/python3`**. On other machines, use the venv that runs the portal host, or adjust the command and **update the task YAML** to match.
- **Deploy-truth script env (optional overrides):** see header of **`scripts/verify_v2_portal_deploy_truth.sh`** — `MYCITE_CORE`, `SRV_INFRA` (default `/srv/repo/srv-infra`), `PORTAL_BASE_URL`, `PORTAL_SYSTEMD_UNIT`, `FND_PORTAL_LOOPBACK`, `VERIFY_DEPLOY_TRUTH_SKIP_HOST`, `VERIFY_DEPLOY_TRUTH_ALLOW_PARTIAL`, `NGINX_BIN`. For **verifier closure** on deploy/live tasks, do **not** rely on `SKIP_HOST` without an explicit task waiver (script exits `4` when skip is incomplete).

---

## Failure semantics

1. Run **Step 1** to completion. If **any** `unittest` fails, **stop** — exit code non-zero — and **do not** treat Step 2 as authoritative.
2. Run **Step 2** only after Step 1 succeeds. If Step 2 fails, the gate fails even if Step 1 previously passed on an older revision.
3. **Lead / closure:** Per **`closure_rule`** on T-006, both legs must **pass** in **verifier** evidence for the task to close.

---

## Step 1 — Repo tests (unittest sweep)

Runs `unittest discover` over **`MyCiteV2/tests/adapters`**, **`architecture`**, **`contracts`**, **`integration`**, **`unit`** — same surface as portal CI regression, including **`test_v2_native_portal_host`** and portal boundary tests.

**Command (must match task YAML exactly):**

```bash
cd /srv/repo/mycite-core &&
for d in MyCiteV2/tests/adapters MyCiteV2/tests/architecture MyCiteV2/tests/contracts MyCiteV2/tests/integration MyCiteV2/tests/unit; do
  echo "== $d ==" &&
  PYTHONPATH=/srv/repo/mycite-core /srv/venvs/fnd_portal/bin/python3 -m unittest discover -s "$d" -p "test*.py" -v || exit 1;
done
```

**Expected:** Each directory prints `OK`; final shell exit code **0**.

---

## Step 2 — Live smoke + host/nginx alignment (`verify_v2_portal_deploy_truth.sh`)

Runs **`scripts/verify_v2_portal_deploy_truth.sh`** from **`mycite-core`** root. This script **reuses** the T-002 deploy-truth path and checks, in order:

| Layer | What is checked (high level) |
|--------|------------------------------|
| **Repo templates** | `portal.html` markers (`shell-template: v2-composition`, `data-portal-shell-driver`, static hrefs, `build=`), non-empty `v2_portal_shell.js`. |
| **Repo nginx intent** | `srv-infra` `portal.fruitfulnetworkdevelopment.com.conf` readable; `location = /healthz`, `location ^~ /portal/static/`, `location ^~ /portal`, `127.0.0.1:6101` healthz proxy. |
| **Live HTTPS** | `200` for `/portal/static/portal.css` and `/portal/static/v2_portal_shell.js`; **`/healthz`** JSON with schema **`mycite.v2.portal.health.v1`**, **`host_shape`** **`v2_native`**, **`static_url_path`** containing **`/portal/static`**, **`ok: true`**, HTTP **200**. |
| **Portal HTML shell markers** | Prefer edge `/portal/system`; if OAuth/sign-in HTML, fall back to loopback **`http://127.0.0.1:6101`** (or `VERIFY_DEPLOY_TRUTH_LOOPBACK_BASE` / `FND_PORTAL_LOOPBACK`) and assert the same shell markers as in templates. |
| **Host** | `systemctl` for **`mycite-v2-fnd-portal.service`** active/running; **`nginx -T`** effective config vs repo intent (grep-level). |

**Command (must match task YAML exactly):**

```bash
cd /srv/repo/mycite-core &&
bash scripts/verify_v2_portal_deploy_truth.sh
```

**Expected:** `All deploy-truth checks passed.` and exit code **0**.

---

## After running

- Paste **verbatim** command transcripts into **`reports/T-006-implementation.md`** (implementer) or **`reports/T-006-verification.md`** (verifier), per role.
- Do **not** merge “repo passed” and “live passed” into a single narrative without two command blocks.

---

## References

- **`tasks/T-006-operational-smoke-and-regression-gates.yaml`** — lifecycle, `closure_rule`, artifact paths.
- **`tasks/T-002-deploy-truth-automation.yaml`** — origin of `verify_v2_portal_deploy_truth.sh`.
- **`scripts/verify_v2_portal_deploy_truth.sh`** — authoritative behavior for Step 2.
