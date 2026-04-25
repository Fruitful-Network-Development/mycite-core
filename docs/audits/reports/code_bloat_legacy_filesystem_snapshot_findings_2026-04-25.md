# Code Bloat Legacy Filesystem + Snapshot Findings

Date: 2026-04-25

Doc type: `audit-report`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-25`

## Registry

- Stream ID: `STREAM-CODE-BLOAT-FINDINGS-EXECUTION`
- Compatibility initiative ID: `INIT-CODE-BLOAT-FINDINGS-EXECUTION`
- Findings task ID: `TASK-CODE-BLOAT-FINDINGS-002`
- Upstream planning task ID: `TASK-CODE-BLOAT-AUDIT-002`
- Downstream remediation task ID: `TASK-CODE-BLOAT-REMEDIATION-002`
- Source audit plan:
  `docs/audits/code_bloat_legacy_filesystem_snapshot_audit_plan_2026-04-24.md`

## Scope

Classify legacy filesystem adapters, JSON/bootstrap artifacts, and deployed
snapshot data by runtime authority role, runtime reachability, and retention
posture.

## Footprint Measurements

- Repository footprint snapshots:
  - `deployed/`: ~82M
  - `deployed/fnd/data/sandbox`: ~32M
  - `deployed/fnd/data/payloads`: ~1.4M
  - `deployed/fnd/private/utilities`: ~364K
- JSON artifact counts under `deployed/fnd/data`:
  - total: 425
  - sandbox: 411
  - payloads: 9
  - system: 5

## Classification Findings

### 1) Active SQL-authoritative runtime paths (retain)

- SYSTEM/Workbench authoritative datum reads are SQL-primary and fail closed
  when SQL authority is missing.
- Evidence:
  - `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
  - `MyCiteV2/tests/unit/test_portal_shell_sql_authority.py`
  - `docs/audits/reports/portal_legacy_boundary_sql_mos_operationalization_report_2026-04-23.md`

Disposition: `active-retain` (canonical authority path).

### 2) Filesystem adapters that remain runtime-reachable but non-datum (isolate-by-contract)

- Filesystem adapters still exist for explicit non-datum or bounded tool
  support (for example AWS-CSM profile/newsletter/config support and selected
  read-only tool surfaces).
- Architecture boundaries forbid adapter-layer semantic leakage and preserve
  adapter-side constraints.
- Evidence:
  - `MyCiteV2/packages/adapters/filesystem/`
  - `MyCiteV2/tests/architecture/test_filesystem_adapter_boundaries.py`
  - `docs/contracts/tool_operating_contract.md`

Disposition: `active-non-datum` (retained as bounded exceptions, not datum authority).

### 3) Deployed snapshots and sandbox payloads (archive-bounded retain)

- `deployed/fnd/data/sandbox/**` remains the largest retained class and is used
  for tool evidence, fixture parity, and compiled artifact reproducibility.
- No evidence in this audit that these payloads can be deleted outright without
  harming parity and regression checks.
- Evidence:
  - `deployed/fnd/data/sandbox/`
  - `deployed/fnd/data/payloads/`
  - `docs/audits/reports/mos_program_closure_report_2026-04-21.md`
  - `docs/audits/reports/portal_legacy_boundary_sql_mos_operationalization_report_2026-04-23.md`

Disposition: `retain-archival-bounded` with explicit boundary:
- runtime authority is SQL for SYSTEM surfaces;
- retained snapshots are fixture/evidence payloads.

## Removal Candidate Decision

No immediate code deletion candidate was approved in this cycle for
`TASK-CODE-BLOAT-REMEDIATION-002`.

Remediation acceptance is satisfied by:

1. isolating filesystem pathways to explicit non-datum/config and fixture roles,
2. enforcing SQL-authority runtime posture for authoritative SYSTEM surfaces, and
3. documenting snapshot retention boundaries as archival/evidence rather than
   active authority.

## Retention Policy (2026-04-25)

- Keep `deployed/fnd/data/sandbox/**` and `deployed/fnd/data/payloads/**` as
  bounded fixture/evidence classes.
- Keep filesystem adapters only where they serve non-datum tool/config needs.
- Do not permit filesystem fallback as authoritative SYSTEM datum path.
- Future prune actions require per-class rollback notes and explicit parity
  evidence before deletion.

## Remediation Disposition

`TASK-CODE-BLOAT-REMEDIATION-002` can close on evidence: filesystem/bootstrap
surfaces not required for active authority are isolated to explicit fixture or
non-datum classes, deployed snapshot boundaries are documented, and SQL
authority posture remains test-backed.
