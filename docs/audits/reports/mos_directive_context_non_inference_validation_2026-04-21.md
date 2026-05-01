# MOS Directive-Context Non-Inference Validation Audit

Date: 2026-04-21

Doc type: `audit`  
Normativity: `supporting`  
Lifecycle: `completed`  
Last reviewed: `2026-04-21`

## Purpose

Verify that the completed MOS cut-over keeps directive context additive and read-only, and that shared directive overlays are imported only from an explicit manifest rather than inferred from historical CTS-GIS tool files or other repo artifacts.

## Scope

- `MyCiteV2/scripts/migrate_fnd_repo_to_mos_sql.py`
- `MyCiteV2/packages/adapters/sql/directive_context.py`
- `MyCiteV2/packages/tools/workbench_ui/service.py`
- `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`

## Canonical Contract Links

- portal shell contract: `docs/contracts/portal_shell_contract.md`
- route model: `docs/contracts/route_model.md`
- surface catalog: `docs/contracts/surface_catalog.md`
- vocabulary glossary: `docs/contracts/portal_vocabulary_glossary.md`

## Validation Rules

1. Shared directive overlays are imported only from an explicit manifest.
2. Absent that manifest, shared directive snapshot/event counts must remain zero.
3. Runtime may summarize directive overlays but must never mutate authoritative datum rows through directive state.
4. Tool-local CTS-GIS state is not promoted into shared directive canon by heuristic extraction.

## Findings

1. The migration script enforces the explicit-manifest rule.
   - `migrate_fnd_repo_to_mos_sql.py` imports directive context only when `--directive-context-manifest` is supplied.
   - Without that manifest, the reports state that no canonical shared overlays were imported.

2. The real FND migration preserved zero shared directive overlays.
   - `mos_fnd_sql_ingestion_coverage_report_2026-04-21.md` reports:
     - `manifest_supplied = False`
     - `snapshot_imported = 0`
     - `event_imported = 0`
     - `directive_snapshot_count = 0`
     - `directive_event_count = 0`

3. Runtime overlay composition remains additive only.
   - `portal_system_workspace_runtime.py` and `workbench_ui/service.py` read directive context after resolving `version_hash` and optional `hyphae_hash`.
   - Both surfaces present overlay summaries separately from authoritative row payloads.

4. Non-mutation behavior is covered by tests.
   - `test_workbench_ui_runtime.py` verifies that overlay reads leave authoritative rows unchanged.
   - `test_portal_system_workspace_directive_context.py` verifies additive system-workspace projection behavior.

## Evidence

- `MyCiteV2/scripts/migrate_fnd_repo_to_mos_sql.py`
- `docs/audits/reports/mos_fnd_sql_ingestion_coverage_report_2026-04-21.md`
- `MyCiteV2/tests/unit/test_workbench_ui_runtime.py`
- `MyCiteV2/tests/unit/test_portal_system_workspace_directive_context.py`

## Verification

Executed:

- `python3 -m unittest MyCiteV2.tests.unit.test_workbench_ui_runtime`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_system_workspace_directive_context`

## Result

The directive-context non-inference and non-mutation gates are met. Shared directive overlays remain explicit-manifest-only, additive, and read-only with respect to authoritative datum rows.
