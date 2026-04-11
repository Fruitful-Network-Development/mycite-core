# Implementer → Verifier: T-006

## Files changed

- `reports/T-006-smoke-gate.md` — canonical **repo → live** gate; commands copied from **`tasks/T-006-operational-smoke-and-regression-gates.yaml`** `execution.repo_test_command` / `execution.live_check_command`.
- `reports/T-006-implementation.md`
- `reports/handoffs/T-006/implementer_to_verifier.md`

## Commands run

1. **Step 1:** full **`execution.repo_test_command`** — all five test dirs **`OK`**, exit **0** (see implementation report; per-directory summaries omitted for size).
2. **Step 2:** **`cd /srv/repo/mycite-core && bash scripts/verify_v2_portal_deploy_truth.sh`** — **`All deploy-truth checks passed.`**, exit **0** (verbatim excerpt in implementation report).

## Reports written

- `reports/T-006-smoke-gate.md`
- `reports/T-006-implementation.md`

## Unresolved risks

- **Venv path** `/srv/venvs/fnd_portal/bin/python3` is environment-specific; other hosts must align **Python** and **`PYTHONPATH`** or update the task YAML and smoke doc together.
- Edge **`/portal/system`** may be OAuth HTML without session; script uses **loopback** for shell markers — verifier should confirm that is acceptable for their acceptance reading.

## What must be independently verified

1. Run **Step 1** and **Step 2** exactly as in **`reports/T-006-smoke-gate.md`** (must match task YAML).
2. Record **verbatim** output in **`reports/T-006-verification.md`** (use **`reports/templates/verification_report_template.md`**; separate repo / host / live as applicable).
3. **`PASS` / `FAIL`** verdict; **either** step failing fails the gate.

## Recommended next task status

`verification_pending` → verifier sets **`verified_pass`** or **`verified_fail`** and **`verification_result`**; lead may **`resolve`** only per **`closure_rule`**.
