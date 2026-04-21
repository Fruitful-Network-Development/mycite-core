# MOS SQL-Only Authority Activation and Legacy Retirement Audit

Date: 2026-04-21

Doc type: `audit`  
Normativity: `supporting`  
Lifecycle: `completed`  
Last reviewed: `2026-04-21`

## Purpose

Verify `Phase 7` of `docs/plans/master_plan_mos.md`: migrated `SYSTEM` surfaces now run from SQL authority, fail closed when SQL authority is missing or uninitialized, and retain any filesystem-era code only as non-authoritative migration or fixture support.

## Scope

Code scope:

- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
- `MyCiteV2/instances/_shared/runtime/runtime_platform.py`

Validation scope:

- SQL-authority runtime tests
- workspace runtime regression tests
- direct workbench runtime tests
- real FND SQL migration smoke checks against `deployed/fnd/private/mos_authority.sqlite3`

## Canonical Contract Links

- portal shell contract: `docs/contracts/portal_shell_contract.md`
- route model: `docs/contracts/route_model.md`
- surface catalog: `docs/contracts/surface_catalog.md`
- vocabulary glossary: `docs/contracts/portal_vocabulary_glossary.md`

## Findings

1. Migrated `SYSTEM` surfaces require SQL authority and fail closed when the DB is missing or uninitialized.
   - `portal_host/app.py` carries `authority_db_file` through host configuration and maps SQL-readiness errors to `503`.
   - `portal_shell_runtime.py`, `portal_system_workspace_runtime.py`, and `portal_workbench_ui_runtime.py` normalize migrated surface authority to SQL-backed execution and emit readiness errors instead of falling back to legacy datum/audit paths.

2. Public migrated runtime defaults are SQL-only.
   - Migrated `SYSTEM` runtime helpers now default to `authority_mode="sql_primary"` where the parameter remains for compatibility.
   - The direct `workbench_ui` runtime verifies SQL readiness before serving the surface payload.

3. Filesystem-era authority is retired, not active.
   - `FilesystemSystemDatumStoreAdapter` and `FilesystemAuditLogAdapter` are no longer active runtime authority for migrated `SYSTEM` surfaces.
   - Remaining filesystem parsing/bootstrap code is retained only as non-authoritative migration, parity, or fixture support.

4. Portal grants/tool exposure are DB-backed in the active cut-over path.
   - Request bootstrap no longer injects hard-coded default capabilities for the migrated SQL path.
   - Portal scope and tool exposure posture resolve through SQL portal-authority data when SQL authority is active.

5. Retired user-facing legacy modes are no longer part of the migrated posture.
   - Shared runtime no longer advertises or relies on public `filesystem` / `shadow` authority modes for migrated `SYSTEM` execution.
   - `NETWORK` remains an explicit derived-materialization exception outside this SQL datum-authority claim.

## Evidence

- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
- `MyCiteV2/tests/unit/test_portal_shell_sql_authority.py`
- `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
- `MyCiteV2/tests/unit/test_workbench_ui_runtime.py`
- `docs/audits/reports/mos_fnd_sql_ingestion_coverage_report_2026-04-21.md`

## Verification

Executed:

- `python3 -m unittest MyCiteV2.tests.unit.test_portal_shell_sql_authority`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_workspace_runtime_behavior`
- `python3 -m unittest MyCiteV2.tests.unit.test_workbench_ui_runtime`

Smoke-verified against the migrated FND authority DB:

- `document_semantics_count = 409`
- `row_semantics_count = 3133`
- `authoritative_catalog_snapshots = 1`
- `system_workbench_snapshots = 1`
- `publication_summary_snapshots = 1`
- `portal_authority_snapshots = 1`
- `directive_context_snapshots = 0`
- `directive_context_events = 0`

## Result

`Phase 7` is verified complete for the current cut-over scope. Migrated `SYSTEM` runtime authority is SQL-only and fail-closed, while any retained filesystem-era code is explicitly non-authoritative support rather than active runtime authority.
