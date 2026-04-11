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
