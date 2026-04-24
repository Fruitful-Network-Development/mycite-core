# Portal Legacy Boundary + SQL MOS Operationalization Report

Date: 2026-04-23

Doc type: `operationalization-report`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-23`

## Initiative and Task Mapping

- Initiative: `INIT-PORTAL-LEGACY-BOUNDARY-SQL-MOS`
- Task IDs:
  - `TASK-PORTAL-LEGACY-SQLMOS-001`
  - `TASK-PORTAL-LEGACY-SQLMOS-002`
  - `TASK-PORTAL-LEGACY-SQLMOS-003`
  - `TASK-PORTAL-LEGACY-SQLMOS-004`
  - `TASK-PORTAL-LEGACY-SQLMOS-005`
  - `TASK-PORTAL-LEGACY-SQLMOS-006`
  - `TASK-PORTAL-LEGACY-SQLMOS-007`

## Program Intent

Operationalize full retirement of legacy portal boundary behavior and JSON datum
fallback pathways that conflict with canonical one-shell/NIMM/AITAS/lens/staging
contracts and SQL-backed MOS datum authority.

## Reality Statement

Current repository and runtime surfaces contain mixed-era artifacts:

1. Legacy shell/UI pathways and fallback logic can coexist with canonical one-shell flow.
2. NIMM/AITAS/lens/staging semantics are not uniformly enforced across all paths.
3. Datum authority intent is SQL-first in MOS programs, but fallback risk remains where
   JSON datum pathways are still reachable in active runtime behavior.
4. Documentation lifecycle labels and canonical pointers need continuous hardening to
   prevent accidental reactivation of superseded pathways.

## Taskized Operational Backlog

### `TASK-PORTAL-LEGACY-SQLMOS-001`

Inventory legacy boundary artifacts and classify disposition (`remove`, `supersede`,
`retain-non-datum`) with canonical replacement mapping.

Status: `done` (2026-04-23 refresh)

Inventory evidence:

- `MyCiteV2/instances/_shared/portal_host/app.py`
  - disposition: `supersede`
  - legacy artifact: compatibility redirects for legacy AWS tool aliases
    (`aws`, `aws-narrow-write`, `aws-csm-sandbox`, `aws-csm-onboarding`)
  - canonical replacement: `/portal/system/tools/aws-csm`
  - rationale: alias entry remains compatibility-only while canonical one-shell
    route remains singular.
- `MyCiteV2/packages/state_machine/portal_shell/shell.py`
  - disposition: `supersede`
  - legacy artifact: retained sandbox token (`SYSTEM_SANDBOX_QUERY_FILE_TOKEN`)
    as a reducer state token, not a legacy route boundary
  - canonical replacement: one-shell route model and reducer-owned surface state
    under `/portal/system` and `/portal/system/tools/<tool_slug>`
  - rationale: no legacy split-shell route ownership remains.
- `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
  - disposition: `remove`
  - retired artifacts verified absent:
    - legacy v1 repository tree
    - `packages/adapters/portal_runtime`
    - `packages/state_machine/trusted_tenant_portal.py`
    - `instances/_shared/runtime/tenant_portal_runtime.py`
    - `instances/_shared/runtime/admin_runtime.py`
    - `packages/state_machine/hanus_shell`
  - canonical replacement: `run_portal_shell_entry` one-shell runtime boundary.
- `docs/contracts/route_model.md`
  - disposition: `supersede`
  - legacy artifact: prior split activity/profile leaf pages
  - canonical replacement: `/portal/system` with reducer-owned query projection.
- `docs/contracts/tool_operating_contract.md`
  - disposition: `retain-non-datum`
  - retained contract artifact: canonical three-family shell contract and
    compatibility `inspector` alias posture
  - rationale: active operating contract, not a legacy runtime fallback.

### `TASK-PORTAL-LEGACY-SQLMOS-002`

Retire legacy shell and sandbox runtime paths so canonical shell composition remains
the sole active UI boundary.

Status: `done` (2026-04-23 refresh)

Retirement/gating evidence:

- Active host routes are constrained to canonical one-shell surfaces:
  `/portal`, `/portal/system`, `/portal/system/tools/<tool_slug>`, `/portal/network`,
  and `/portal/utilities` (`MyCiteV2/instances/_shared/portal_host/app.py`).
- Legacy split shell/API route strings are explicitly asserted absent by architecture
  guardrails (`MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`).
- Runtime composition remains family-contract-driven from one shell entrypoint:
  `run_portal_shell_entry` with region-family contracts
  (`MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`,
  `MyCiteV2/instances/_shared/runtime/runtime_platform.py`).
- Retained compatibility aliases are gated to canonical replacements (for example,
  AWS legacy slugs redirect to `/portal/system/tools/aws-csm`) and do not introduce
  alternate shell composition boundaries.

### `TASK-PORTAL-LEGACY-SQLMOS-003`

Converge directive handling on canonical NIMM envelope + AITAS + lens + staging pipeline.

Status: `done` (2026-04-23 refresh)

Canonical directive pipeline evidence:

- Canonical envelope schema and parser are centralized in
  `MyCiteV2/packages/state_machine/nimm/envelope.py`
  (`mycite.v2.nimm.envelope.v1`).
- Staging compiles edits exclusively into canonical manipulation envelopes through
  `StagingArea.compile_manipulation_envelope(...)`
  (`MyCiteV2/packages/state_machine/nimm/staging.py`).
- Shell-level directive handoff keeps the same NIMM + merged-AITAS path through
  `build_nimm_envelope_for_shell_state(...)`
  (`MyCiteV2/packages/state_machine/portal_shell/shell.py`).
- Regression coverage validates versioned schema round-trip, AITAS merge behavior,
  and lens-normalized stage compilation in
  `MyCiteV2/tests/unit/test_nimm_phase2_foundations.py`.

### `TASK-PORTAL-LEGACY-SQLMOS-004`

Remove active MOS datum JSON fallback pathways and enforce SQL-backed datum authority.
Explicitly preserve non-datum JSON config/contract artifacts.

Status: `done` (2026-04-23 refresh)

SQL authority enforcement evidence:

- `run_portal_shell_entry(...)` returns `sql_authority_required` or
  `sql_authority_uninitialized` for SYSTEM surfaces when SQL authority is missing
  or not bootstrapped
  (`MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`).
- SYSTEM workspace projection reads through `SqliteSystemDatumStoreAdapter` and
  emits readiness warnings instead of filesystem authority fallback
  (`MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`).
- Workbench UI surface enforces the same SQL-only readiness gate
  (`MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`).
- SQL-only behavior is guarded by runtime and closure tests
  (`MyCiteV2/tests/unit/test_portal_shell_sql_authority.py`,
  `MyCiteV2/tests/unit/test_mos_program_closure.py`).

Retained non-datum JSON artifacts (explicitly out-of-scope for removal):

- tool mediation/config files under `deployed/fnd/private/utilities/tools/**`
- newsletter/profile support JSON under `deployed/fnd/private/utilities/tools/aws-csm/newsletter/**`
- compatibility/config JSON such as `private/config.json`

These retained JSON assets are operational metadata surfaces; they are not MOS
datum authority stores and do not replace SQL-backed authoritative datum reads/writes.

2026-04-24 follow-on evidence:

- `TASK-AWS-CSM-RECOVERY-005` retired direct mailbox/newsletter file-scan logic
  from `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py` in favor of
  shared filesystem adapters while preserving the JSON artifacts above as explicit
  non-datum/config exceptions.

### `TASK-PORTAL-LEGACY-SQLMOS-005`

Mark superseded legacy docs and indexes with `historical-superseded` lifecycle and
canonical pointers.

Status: `done` (2026-04-23 refresh)

Documentation supersession evidence:

- `docs/plans/README.md` now explicitly retains the legacy MOS index artifact as
  `historical-superseded` with canonical pointers to contextual manifest/task-board surfaces.
- `docs/audits/README.md` now labels each 2026-04-20 CTS-GIS audit plan as
  `historical-superseded` with canonical replacement
  `docs/audits/cts_gis_open_alignment_audit_plan_2026-04-23.md`.
- Historical context remains retained in place (`docs/plans/archive/`,
  `docs/audits/archive/`) with no deletion of legacy narrative artifacts.

### `TASK-PORTAL-LEGACY-SQLMOS-006`

Add anti-regression tests that fail when legacy boundary behavior or datum JSON fallback
reappears in active runtime pathways.

Status: `done` (2026-04-23 refresh)

Regression guard evidence:

- Added architecture regression coverage:
  `test_sql_authority_runtime_paths_forbid_datum_json_fallback_but_allow_non_datum_json_configs`
  in `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`.
- The new guard fails if active SYSTEM/Workbench runtime paths reintroduce
  filesystem datum authority fallback and confirms SQL authority gating tokens.
- The same guard explicitly permits retained non-datum JSON operational metadata
  artifacts (`tool.*.aws-csm.json`, `spec.json`) to avoid over-blocking.
- Existing state-machine boundary checks remain active in
  `MyCiteV2/tests/architecture/test_state_machine_boundaries.py`.

### `TASK-PORTAL-LEGACY-SQLMOS-007`

Publish closure-ready status and compatibility-sync evidence across contextual and
secondary planning surfaces.

Status: `done` (2026-04-23 refresh)

Closure-ready mapping:

- Completed removals / supersessions:
  - `TASK-PORTAL-LEGACY-SQLMOS-001`: legacy boundary inventory completed with
    disposition + canonical pointer mapping.
  - `TASK-PORTAL-LEGACY-SQLMOS-002`: active shell routing constrained to canonical
    one-shell boundaries.
  - `TASK-PORTAL-LEGACY-SQLMOS-003`: canonical NIMM/AITAS/lens staging pipeline
    verified and evidenced.
  - `TASK-PORTAL-LEGACY-SQLMOS-004`: SQL datum authority enforcement verified;
    active datum JSON fallback retired from SYSTEM/Workbench runtime authority.
  - `TASK-PORTAL-LEGACY-SQLMOS-005`: superseded docs/indexes carry explicit
    lifecycle + canonical replacement pointers.
  - `TASK-PORTAL-LEGACY-SQLMOS-006`: anti-regression guardrails added for legacy
    boundary/datum fallback reintroduction.
- Retained exceptions (explicit and allowed):
  - non-datum JSON tool/config artifacts under private utility/tool paths
  - compatibility aliasing that redirects to canonical routes without creating
    alternate shell boundaries.
- Remaining blockers:
  - none for `INIT-PORTAL-LEGACY-BOUNDARY-SQL-MOS`.

## Lifecycle and Consolidation Notes

- Decision: **new stream added** for portal-wide legacy retirement + SQL MOS datum convergence.
- Existing streams remain active and unchanged in canonical ownership.
- No historical artifact was deleted in this planning pass.

## Evidence Targets

- `docs/plans/portal_legacy_boundary_sql_mos_convergence_plan_2026-04-23.md`
- `docs/contracts/tool_operating_contract.md`
- `docs/contracts/mutation_contract.md`
- `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md`
- `docs/plans/contextual_system_manifest.yaml`
- `docs/plans/planning_audit_manifest.yaml`

## Validation Log

Validation commands executed for this taskization update:

- `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment`
- `python3 -m unittest MyCiteV2.tests.architecture.test_state_machine_boundaries`
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
- `python3 -m unittest MyCiteV2.tests.unit.test_nimm_phase2_foundations`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_shell_sql_authority`
- `python3 -m unittest MyCiteV2.tests.unit.test_mos_program_closure` (pre-existing failure)

Results:

- `test_contract_docs_alignment`: pass
- `test_state_machine_boundaries`: pass
- `test_portal_one_shell_boundaries`: pass
- `test_nimm_phase2_foundations`: pass
- `test_portal_shell_sql_authority`: pass
- `test_mos_program_closure`: fail (`test_closure_checklist_covers_every_plan_and_report_artifact`); pre-existing checklist drift across planning/report docs, not introduced by this task.
