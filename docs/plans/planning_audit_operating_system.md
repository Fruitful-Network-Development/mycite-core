# Planning + Audit Operating System

Date: 2026-04-23

Doc type: `system-guide`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-25`

## Purpose

Define one canonical operating model for planning and closure work across:

- `docs/plans/`
- `docs/audits/`
- `docs/audits/reports/`

This document makes the three directories function as one tool by requiring one
shared YAML manifest and one shared YAML task board.

## Canonical Control Surfaces

1. `docs/plans/contextual_system_manifest.yaml`
   - contextual entrypoint truth for `plans/`, `audits/`, and `audits/reports/`
   - canonical stream-level mapping (one active plan + one active report per stream)
   - regression analysis requirements used for closure
2. `docs/plans/contextual_system_task_board.yaml`
   - execution-level organization truth for contextual-system maintenance
   - consolidation, archival, and evidence mapping tasks
3. Compatibility surfaces (retained):
   - `docs/plans/planning_audit_manifest.yaml`
   - `docs/plans/planning_task_board.yaml`
   - these remain supported but are no longer the primary navigation entrypoints

The markdown files remain narrative implementation and evidence artifacts, but
contextual navigation and organization transitions now flow through the contextual
manifest + contextual task board first.

## Lifecycle Flow

1. Define or update canonical stream mapping in `contextual_system_manifest.yaml`.
2. Open/refresh organization tasks in `contextual_system_task_board.yaml`.
3. Execute implementation or audit work in referenced plan/audit docs.
4. Publish evidence in `docs/audits/reports/`.
5. Close tasks (`status: done`) when acceptance criteria are evidenced.
6. Sync compatibility surfaces (`planning_audit_manifest.yaml`, `planning_task_board.yaml`).
7. Move initiative lifecycle to `completed` or `historical-superseded`.
8. Archive superseded planning docs and keep only canonical references active.

## YAML-First Extension Rule

For new cross-directory work, update the contextual manifest and task board
before publishing markdown plans or reports. Compatibility surfaces must be
updated in the same change when a new stream, initiative, task ID, canonical
plan, or canonical report is introduced.

When a completed stream is the foundation for new work, create a new active
stream instead of reopening the completed stream unless the old closure record
was materially wrong. Retain the completed plan/report as evidence and link the
new stream to it.

Current application: completed `STREAM-CODE-BLOAT-DEEP-AUDIT` seeds active
`STREAM-CODE-BLOAT-REMEDIATION`, preserving diagnosis/planning history while
tracking corrective execution tasks with one canonical active plan and one
canonical active report.

## Consolidation Rule

When multiple active docs describe one workstream, keep one canonical active plan and
demote the others to `historical-superseded` with explicit pointers to the canonical file.

## Closure Rule

An initiative can only be closed when all linked tasks are `done` and every closure gate
has evidence paths in `docs/audits/reports/` or explicitly recorded waivers.

## Required Maintenance

- Update `Last reviewed` on any touched plan/audit/report.
- Keep manifest/task IDs stable; never reuse closed task IDs for new work.
- Keep plan/audit/report links resolvable and repo-relative.
- Keep archive notes explicit when demoting lifecycle state.

## Reusable Delegation Loop

Use one reusable prompt to advance the next actionable item every cycle.

Delegation source of truth:

- `manifest.delegation_protocol` in:
  - `docs/plans/contextual_system_manifest.yaml`
  - `docs/plans/planning_audit_manifest.yaml`
- `board.delegation_state` in:
  - `docs/plans/contextual_system_task_board.yaml`
  - `docs/plans/planning_task_board.yaml`

Loop rules:

1. Select exactly one next task from active streams/initiatives using:
   - status order: `in_progress` -> `pending` -> `blocked`
   - priority order: `p0` -> `p1` -> `p2` -> `p3`
   - tiebreaker: lexicographically earliest stable task ID
2. If selected task is `blocked`, perform unblock taskization and evidence mapping first.
3. If execution findings require revisit, inject new stable task IDs and add them to both task boards and both manifests in the same change.
4. Keep one canonical active plan + one canonical active report per active stream.
5. Report cycle output with:
   - files changed
   - task IDs updated/added
   - lifecycle/consolidation decisions
   - validations executed
