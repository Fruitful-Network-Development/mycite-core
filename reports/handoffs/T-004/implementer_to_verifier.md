# Implementer → Verifier: T-004

## Files changed

- `reports/templates/implementation_report_template.md`
- `reports/templates/verification_report_template.md`
- `agent/lead.md`
- `tasks/README.md`

## Commands run

- None (`repo_test_command: not_applicable`).

## Reports written

- `reports/T-004-implementation.md` (this cycle)
- Templates updated in place under `reports/templates/`

## Unresolved risks

- None known; scope is repo-only documentation and templates.

## What must be independently verified

1. Templates remain **short and operational**, with **separate repo / host / live** sections and clear behavior for **`repo_only`** vs **`repo_and_deploy`**.
2. **Verification template** retains a **required final verdict** (`PASS` / `FAIL`).
3. **Role separation:** implementer template vs verifier template; lead **closure** text now states verifier report + transcripts are mandatory when non-repo truth gates closure.
4. **At least one example task** with both artifact paths: see `tasks/T-002-deploy-truth-automation.yaml`, `tasks/T-003-shell-region-contracts.yaml`, `tasks/T-004-evidence-artifacts-and-verification.yaml` (`artifacts` + `execution.reports`).

## Recommended next task status

- `status: verification_pending`
- `execution.current_role: verifier`
- `execution.next_role: lead`
- `verification_result: pending` until you record `pass` or `fail`

Please write `reports/T-004-verification.md` using `reports/templates/verification_report_template.md` and `reports/handoffs/T-004/verifier_to_lead.md` per `tasks/README.md`.
