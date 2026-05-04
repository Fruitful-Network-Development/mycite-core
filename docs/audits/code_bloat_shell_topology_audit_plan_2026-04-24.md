# Code Bloat Shell Topology Audit Plan

Date: 2026-04-24

Doc type: `audit-plan`
Normativity: `planning`
Lifecycle: `active`
Last reviewed: `2026-04-24`

## Registry

- Stream ID: `STREAM-CODE-BLOAT-DEEP-AUDIT`
- Compatibility initiative ID: `INIT-CODE-BLOAT-DEEP-AUDIT`
- Task ID: `TASK-CODE-BLOAT-AUDIT-001`
- Source report: `docs/audits/reports/code_bloat_diagnosis.md`
- Status: planning only; audit not executed.

## Audit Objective

Determine which shell entrypoints, renderer families, region payload builders,
and first-load branches are still active, which are compatibility shims, and
which are historical bloat that can be retired without reopening completed
one-shell work.

## Goes Further Than Diagnosis

The diagnosis identifies multi-shell complexity. This plan requires concrete
runtime reachability proof, payload ownership mapping, route-to-renderer traces,
and regression guard design before any deletion recommendation.

## Evidence Targets

- `docs/plans/one_shell_portal_refactor.md`
- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/packages/state_machine/portal_shell/shell.py`
- `MyCiteV2/instances/_shared/portal_host/static/`

## Audit Procedure

1. Inventory every route that produces shell composition or tool-region payloads.
2. Build a reachability matrix for shell entrypoints, renderer families, and
   region payload types from app route to frontend renderer.
3. Classify each branch as canonical active, compatibility alias, test-only,
   deployment-only, or historical candidate.
4. Capture first-load timing and payload composition evidence for each canonical
   route family.
5. Identify duplicate normalization or branching hidden inside renderer
   dispatch, but defer detailed normalization closure to
   `TASK-CODE-BLOAT-AUDIT-006`.
6. Define required regression guards before recommending removal or demotion.

## Acceptance Criteria

- Active versus historical shell paths are cataloged with file-level evidence.
- Deletion or consolidation candidates include owner, risk, and regression gate.
- Findings report links to `TASK-CODE-BLOAT-AUDIT-001` and
  `STREAM-CODE-BLOAT-DEEP-AUDIT`.
