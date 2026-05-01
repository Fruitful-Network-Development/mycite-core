# Code Bloat Legacy Filesystem Snapshot Audit Plan

Date: 2026-04-24

Doc type: `audit-plan`
Normativity: `planning`
Lifecycle: `active`
Last reviewed: `2026-04-24`

## Registry

- Stream ID: `STREAM-CODE-BLOAT-DEEP-AUDIT`
- Compatibility initiative ID: `INIT-CODE-BLOAT-DEEP-AUDIT`
- Task ID: `TASK-CODE-BLOAT-AUDIT-002`
- Source report: `docs/audits/reports/code_bloat_diagnosis.md`
- Status: planning only; audit not executed.

## Audit Objective

Classify legacy filesystem adapters, JSON bootstrap artifacts, retained
migration fixtures, and deployed snapshots by authority, runtime reachability,
test value, archival value, and removal readiness.

## Goes Further Than Diagnosis

The diagnosis points at leftover filesystem and snapshot bloat. This plan
requires datum-authority proof, retained-exception rationale, repository-size
accounting, runtime-load evidence, and historical preservation decisions before
any pruning recommendation.

## Evidence Targets

- `docs/audits/reports/portal_legacy_boundary_sql_mos_operationalization_report_2026-04-23.md`
- `docs/audits/reports/mos_program_closure_report_2026-04-21.md`
- `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md`
- `MyCiteV2/`
- `deployed/`
- `docs/plans/contextual_system_manifest.yaml`

## Audit Procedure

1. Inventory JSON and filesystem read/write sites in active runtime, adapters,
   tests, scripts, and deployed snapshots.
2. Separate SQL-authoritative datum paths from non-datum configuration,
   deployment, fixture, and archival artifacts.
3. Measure repository footprint for deployed snapshots and large retained
   artifacts.
4. Trace startup and request paths to prove whether each filesystem path can
   execute in normal portal operation.
5. Identify artifacts that should be archived, moved out of runtime reach,
   retained as fixtures, or marked historical-superseded.
6. Define rollback and historical recovery requirements for any prune candidate.

## Acceptance Criteria

- Every reviewed filesystem/snapshot class has an active, test-only, archival,
  or removable disposition.
- Retained JSON exceptions are explicitly non-datum or migration/fixture scoped.
- Findings report links to `TASK-CODE-BLOAT-AUDIT-002` and
  `STREAM-CODE-BLOAT-DEEP-AUDIT`.
