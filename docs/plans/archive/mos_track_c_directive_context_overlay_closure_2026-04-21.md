# MOS Track C Directive-Context Overlay Closure Artifact

Date: 2026-04-21

Doc type: `policy`  
Normativity: `supporting`  
Lifecycle: `historical-superseded`  
Last reviewed: `2026-04-21`

## Purpose

Record the implemented Track C runtime posture for directive-context overlays so the SQL-backed core can compose normalized NIMM/AITAS-adjacent state without turning directive context into datum authority.

## Supersession Note

This artifact remains retained as historical Track C evidence. The completed MOS closure state, including the `workbench_ui` additive read surface and the explicit non-inference migration rule, is recorded in:

- `docs/plans/master_plan_mos.md`
- `docs/plans/mos_directive_context_design_track_2026-04-21.md`
- `docs/audits/reports/mos_directive_context_non_inference_validation_2026-04-21.md`
- `docs/audits/reports/mos_program_closure_report_2026-04-21.md`

## Implemented Scope

The approved Track C implementation pass now includes:

- additive SQL tables:
  - `directive_context_snapshots`
  - `directive_context_events`
- a bounded port package:
  - `MyCiteV2/packages/ports/directive_context/`
- a SQL adapter:
  - `MyCiteV2/packages/adapters/sql/directive_context.py`
- one approved shared runtime seam:
  - system workspace composition in `portal_system_workspace_runtime.py`

## Canonical Read Model

1. Directive context is read only after the SQL datum store resolves:
   - document `version_hash`
   - row `hyphae_hash` when a datum is selected
2. Runtime requests use:
   - `portal_instance_id`
   - `tool_id=system_workspace`
   - `subject_version_hash`
   - optional `subject_hyphae_hash`
3. Snapshot resolution prefers:
   - exact `hyphae_hash + version_hash`
   - then stable-subject or version-only fallback snapshots
4. The runtime composes the overlay into additive payload fields and inspector sections only.

## Non-Mutation Rules

1. Directive context must never rewrite authoritative datum rows.
2. Directive context must never replace the SQL datum-store semantic identities it depends on.
3. Missing directive context must not block file/workbench rendering.
4. Event history is append only and not treated as the authoritative datum store.

## Approved Runtime Output

For the current implementation pass, the system workspace may expose:

- `workspace.document.directive_context`
- a `Directive context` inspector section

These are additive summaries only. The selected datum payload and raw row content remain unchanged.

## Evidence

- `MyCiteV2/packages/ports/directive_context/contracts.py`
- `MyCiteV2/packages/adapters/sql/directive_context.py`
- `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
- `MyCiteV2/tests/contracts/test_directive_context_contracts.py`
- `MyCiteV2/tests/adapters/test_sql_directive_context_adapter.py`
- `MyCiteV2/tests/unit/test_portal_system_workspace_directive_context.py`

## Closure Statement

Track C is closed for this implementation pass because the repo now has a concrete, non-blocking, read-only directive overlay model with explicit SQL storage, event logging, runtime composition rules, and regression coverage, while shared-engine directive canon remains intentionally deferred.
