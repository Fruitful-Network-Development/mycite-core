# Lead → Implementer: T-008 AWS-CSM sandbox tool orchestration and shell surface

## Task classification

- **primary_type:** `repo_only` (confirmed per task YAML: `live_systems: []`, `live_check_command: not_applicable`). **Verifier is still required** (`execution.requires_verifier: true`). Closure needs **`verification_result: pass`**, **`reports/T-008-verification.md`** with **verbatim** transcripts for the **repo test** section, plus **`reports/T-008-implementation.md`** per `closure_rule`. Host/live report sections may state **`not applicable`** where unchanged.

## Investigation bus (read first)

- **`reports/T-007-investigation.md`** (`artifacts.investigation_reference`) — repo findings, gaps, and **§8** list of paths likely to change. Treat as **evidence**, not authority over `structural_invariants.md` or ADRs.

## Authority (read in task order)

1. `MyCiteV2/docs/ontology/structural_invariants.md`
2. `MyCiteV2/docs/decisions/decision_record_0006_sandboxes_are_orchestration_boundaries.md`
3. `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/read_only_and_bounded_write_patterns.md`
4. `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/future_tool_drop_in_contract.md`
5. `MyCiteV2/docs/contracts/shell_region_kinds.md`

Then implement against scoped code (expand only as needed):

- `MyCiteV2/packages/sandboxes/tool/` (today: placeholder `README.md` + `__init__.py` — replace placeholder with real orchestration for **staged `aws_csm.profile.v1`** handling per task objective).
- `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py` — registry, dispatch bodies, composition; **distinct** sandbox descriptor vs existing **trusted-tenant** AWS read-only and narrow-write entries (`build_admin_tool_registry_entries` / successors).
- `MyCiteV2/instances/_shared/runtime/admin_runtime.py`, `admin_aws_runtime.py` — shell-approved entrypoints, fail-closed paths when sandbox roots/profiles missing or invalid.
- `MyCiteV2/instances/_shared/portal_host/app.py`, `.../static/v2_portal_shell.js` — only if the drop-in contract requires new HTTP surfaces or client branches; document any new route/env next to **`MYCITE_V2_AWS_STATUS_FILE`** / **`_required_live_aws_status_file`** semantics per `implementation_requirements`.
- `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/` — **new slice file** for the sandbox tool (band, gates, slice id) per `required_outputs`.
- `MyCiteV2/tests/` — unit + integration + **architecture** tests (import boundaries; sandbox does not pull forbidden packages — existing **`test_state_machine_boundaries`** family must keep passing).

## Exact goal

Deliver a **V2-legal** AWS-CSM **sandbox** workflow that:

1. **Orchestrates** under `MyCiteV2/packages/sandboxes/tool/` only what ADR 0006 allows (orchestration boundary; modules own semantics; adapters thin).
2. Registers a **third** admin tool surface **separate** from `admin_band1.aws_read_only_surface` and `admin_band2.aws_narrow_write_surface` — **no regression** to their slice IDs, entrypoints, or behavior.
3. Wires **runtime + shell composition** so launch and navigation stay **shell-owned** (registry + catalog + dispatch bodies); **fail-closed** when sandbox profile roots or staged profiles are missing/invalid.
4. Adds **pytest/unittest** coverage per acceptance (targets in **`execution.repo_test_command`** must pass); **append** new unittest module paths to that **single canonical** string whenever you add automated tests (`implementation_requirements`).
5. Updates **`MyCiteV2/docs/contracts/shell_region_kinds.md`** only if the code actually emits **new** region kinds or routes.

## Constraints that matter

- **Do not** copy `MyCiteV1/packages/tools/aws_csm` as a structural template; V1 is evidence only (`implementation_requirements`).
- **Browser JS and adapters are not alternate shell truth** — `shell_composition` and registry remain canonical (`objective`, `structural_invariants`).
- **Bounded write** (if any): explicit field set, read-after-write, local audit per existing **`AdminToolRegistryEntry`** rules for write tools.
- **Repo handoff bus:** write **`reports/T-008-implementation.md`**, **`reports/handoffs/T-008/implementer_to_verifier.md`**, and update task YAML for handoff; do not rely on chat for evidence.

## Required outputs

1. **Code + docs** satisfying every **`acceptance`** bullet in `tasks/T-008-aws-csm-sandbox-tool.yaml`.
2. **`reports/T-008-implementation.md`** — use `reports/templates/implementation_report_template.md`; separate repo / host / live (host/live `not applicable` where appropriate).
3. **`reports/handoffs/T-008/implementer_to_verifier.md`** — files changed, commands run, exact **`execution.repo_test_command`** string after edits, what verifier must rerun, production-AWS regression risks.
4. **Task YAML:** when handing off to verifier: `status: verification_pending`, `execution.current_role: verifier`, `execution.next_role: lead`. **Update `execution.repo_test_command`** to include every new unittest module path in one string. Do **not** set `verification_result` or `resolved`.

## Stop conditions

- If ADR 0006 vs `future_tool_drop_in_contract` conflicts with a chosen shape, document in implementation report and set **`blocked`** rather than guessing.
- If adding portal routes without documenting env interaction with **`_required_live_aws_status_file`**, treat as **incomplete** — fix before `verification_pending`.

## Recommended next task status after implementation

- `status: verification_pending`
- `execution.current_role: verifier`
- `execution.next_role: lead`
- `verification_result: pending`
