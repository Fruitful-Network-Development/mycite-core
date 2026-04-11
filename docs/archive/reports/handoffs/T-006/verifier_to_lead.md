# Verifier → Lead: T-006

## Verification commands used

1. **Step 1** — full **`execution.repo_test_command`** from **`tasks/T-006-operational-smoke-and-regression-gates.yaml`** (stdout captured to **`/tmp/T-006-verifier-repo-tests.log`**, **`repo_step_exit=0`**). Full transcript is in **`reports/T-006-verification.md`** §5.1.
2. **Step 2** — full **`execution.live_check_command`**: `cd /srv/repo/mycite-core && bash scripts/verify_v2_portal_deploy_truth.sh` (stdout to **`/tmp/T-006-verifier-live-smoke.log`**, **`live_step_exit=0`**). Full transcript in **`reports/T-006-verification.md`** §5.2.

## Evidence summary

- **`reports/T-006-smoke-gate.md`** documents repo-first then live-second gate, matches task YAML commands, and maps Step 2 to shell markers, static URLs, health JSON / bundle, nginx, and systemd.
- Verifier re-ran both steps successfully on **2026-04-11**; no drift between implementer claims and verifier transcripts (independent runs).

## Verdict

**PASS**

## Mismatches

None.

## Recommended final status

- `status: verified_pass`, `verification_result: pass`, `execution.current_role: lead`, `execution.next_role: lead`
- Lead may set `status: resolved` per **`closure_rule`** when satisfied.
