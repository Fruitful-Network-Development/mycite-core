# Code Bloat Deep Audit Program Plan

Date: 2026-04-24

Doc type: `program-plan`
Normativity: `planning`
Lifecycle: `active`
Last reviewed: `2026-04-24`

## Planning Registry

- Stream ID: `STREAM-CODE-BLOAT-DEEP-AUDIT`
- Compatibility initiative ID: `INIT-CODE-BLOAT-DEEP-AUDIT`
- Canonical report seed: `docs/audits/reports/code_bloat_diagnosis.md`
- Scope posture: create deeper audit plans only; do not execute the audits in this pass.

## Purpose

Convert the broad code-bloat diagnosis into seven deeper, executable audit plans
with stable YAML task tracking, evidence targets, and clear closure gates. This
plan is the canonical active stream plan so the seven task-level audit plans do
not create competing canonical streams.

## Audit Plan Set

1. `TASK-CODE-BLOAT-AUDIT-001` - shell topology and renderer-family bloat:
   `docs/audits/code_bloat_shell_topology_audit_plan_2026-04-24.md`
2. `TASK-CODE-BLOAT-AUDIT-002` - legacy filesystem and deployed snapshots:
   `docs/audits/code_bloat_legacy_filesystem_snapshot_audit_plan_2026-04-24.md`
3. `TASK-CODE-BLOAT-AUDIT-003` - Python import graph and module modularity:
   `docs/audits/code_bloat_python_import_modularity_audit_plan_2026-04-24.md`
4. `TASK-CODE-BLOAT-AUDIT-004` - data I/O, payload sizing, caching, and async
   boundaries: `docs/audits/code_bloat_data_io_caching_audit_plan_2026-04-24.md`
5. `TASK-CODE-BLOAT-AUDIT-005` - frontend bundle and asset loading:
   `docs/audits/code_bloat_frontend_bundle_audit_plan_2026-04-24.md`
6. `TASK-CODE-BLOAT-AUDIT-006` - normalization drift and duplicated helpers:
   `docs/audits/code_bloat_normalization_drift_audit_plan_2026-04-24.md`
7. `TASK-CODE-BLOAT-AUDIT-007` - test fixture, tooling, and regression
   economics: `docs/audits/code_bloat_test_tooling_overhead_audit_plan_2026-04-24.md`

## Lifecycle Decision

This is a new active stream. Existing completed streams for one-shell closure,
SQL MOS convergence, AWS-CSM recovery, and NIMM/AITAS unification remain closed
and serve as evidence inputs. The existing bloat diagnosis remains the canonical
seed report until the deep audits publish a consolidated findings report.

## Closure Expectations

Each audit plan must produce a future report that links back to its
`TASK-CODE-BLOAT-AUDIT-*` ID and the parent stream. Tasks stay `pending` until
their audit is executed, evidence is published, and acceptance criteria are met.
