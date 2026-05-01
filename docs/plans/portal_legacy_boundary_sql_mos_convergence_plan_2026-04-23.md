# Portal Legacy Boundary + SQL MOS Convergence Plan

Date: 2026-04-23

Doc type: `plan`
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

## Purpose

Retire legacy portal-shell/UI/documentation paths that conflict with the current
one-shell boundary model and converge active datum authority on SQL-backed MOS
datum pathways, while preserving non-datum JSON configuration/contract artifacts.

## Canonical Contract Links

- `docs/contracts/tool_operating_contract.md`
- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/mutation_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`

## Scope

1. Legacy boundary inventory across shell, runtime, scripts, and docs.
2. Removal/supersession of legacy shell sandbox and UI fallback paths.
3. Convergence of NIMM/AITAS/lens/staging usage onto canonical directive pipeline.
4. Retirement of MOS datum JSON fallback paths from active runtime behavior.
5. Preservation and explicit retention of non-datum JSON tool/config artifacts.
6. Regression and closure reporting for long-term guardrail enforcement.

## Out-of-Scope Clarification

- JSON files that are not datum authority surfaces (tool state, contracts,
  configuration, manifests, and compatibility artifacts) are retained unless they
  are independently superseded by canonical replacements.

## Execution Sequence

1. Complete inventory and classify each legacy artifact (`TASK-PORTAL-LEGACY-SQLMOS-001`).
2. Remove/gate shell and sandbox fallbacks from active routing (`TASK-PORTAL-LEGACY-SQLMOS-002`).
3. Normalize directive pipeline usage (`TASK-PORTAL-LEGACY-SQLMOS-003`).
4. Remove datum JSON fallback pathways and enforce SQL-only active authority (`TASK-PORTAL-LEGACY-SQLMOS-004`).
5. Apply lifecycle labels and archive pointers for superseded docs (`TASK-PORTAL-LEGACY-SQLMOS-005`).
6. Add regression coverage and anti-regression guards (`TASK-PORTAL-LEGACY-SQLMOS-006`).
7. Publish closure-ready operationalization report (`TASK-PORTAL-LEGACY-SQLMOS-007`).

## Evidence Targets

- `docs/audits/reports/portal_legacy_boundary_sql_mos_operationalization_report_2026-04-23.md`
- `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md`
- `docs/plans/contextual_system_manifest.yaml`
- `docs/plans/planning_audit_manifest.yaml`

## Exit Criteria

- Active portal runtime paths adhere exclusively to canonical shell boundaries.
- Active datum authority uses SQL-backed MOS pathways with no runtime JSON datum fallback.
- Retained JSON artifacts are explicitly classified as non-datum and documented.
- Regression suites fail when deprecated boundary/fallback paths reappear.
