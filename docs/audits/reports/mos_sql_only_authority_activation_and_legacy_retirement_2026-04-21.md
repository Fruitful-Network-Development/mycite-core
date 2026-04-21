# MOS SQL-Only Authority Activation and Legacy Retirement Audit

Date: 2026-04-21

Doc type: `audit`  
Normativity: `supporting`  
Lifecycle: `completed`  
Last reviewed: `2026-04-21`

## Purpose

Verify `Phase 7` of `docs/plans/master_plan_mos.md`: migrated `SYSTEM` surfaces now run from SQL authority, fail closed when SQL authority is missing, and no longer use filesystem datum/audit adapters as active shared-runtime authority.

## Scope

Code scope:

- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
- `MyCiteV2/instances/_shared/runtime/runtime_platform.py`

Validation scope:

- SQL-authority runtime tests
- workspace runtime regression tests
- real FND SQL migration smoke checks against `deployed/fnd/private/mos_authority.sqlite3`

## Canonical Contract Links

- portal shell contract: `docs/contracts/portal_shell_contract.md`
- route model: `docs/contracts/route_model.md`
- surface catalog: `docs/contracts/surface_catalog.md`
- vocabulary glossary: `docs/contracts/portal_vocabulary_glossary.md`

## Findings

1. Migrated `SYSTEM` surfaces now require SQL authority.
   - `portal_host/app.py` now carries `authority_db_file` through host configuration and maps SQL-readiness errors to `503`.
   - `portal_shell_runtime.py` and `portal_system_workspace_runtime.py` normalize migrated surface authority to SQL-backed execution and emit explicit readiness errors when the authority DB or required snapshots are missing.

2. Shared runtime no longer treats filesystem datum/audit paths as active authority for migrated `SYSTEM` surfaces.
   - `FilesystemSystemDatumStoreAdapter` and `FilesystemAuditLogAdapter` are no longer used in shared runtime composition for migrated `SYSTEM` surfaces.
   - Remaining filesystem parsing logic is retained only where migration/bootstrap or fixture tests still need it.

3. Portal grants/tool exposure are now DB-backed in the active cut-over path.
   - Request bootstrap no longer injects hard-coded default capabilities for the migrated SQL path.
   - Portal scope and tool exposure posture now resolve through SQL portal-authority data when SQL authority is active.

4. The retired modes are no longer public runtime posture for migrated surfaces.
   - Shared runtime no longer advertises or relies on `filesystem` / `shadow` authority modes for migrated `SYSTEM` execution.
   - `NETWORK` remains an explicit derived-materialization exception outside this SQL datum-authority claim.

## Evidence

- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
- `MyCiteV2/tests/unit/test_portal_shell_sql_authority.py`
- `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
- `docs/audits/reports/mos_fnd_sql_ingestion_coverage_report_2026-04-21.md`

## Verification

Executed:

- `python3 -m unittest MyCiteV2.tests.unit.test_portal_shell_sql_authority`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_workspace_runtime_behavior`

Smoke-verified against the migrated FND authority DB:

- `system.root` returned `error=null`
- `system.tools.workbench_ui` returned `error=null`
- SQL authority counts included:
  - `authoritative_catalog_snapshots = 1`
  - `system_workbench_snapshots = 1`
  - `publication_summary_snapshots = 1`
  - `portal_authority_snapshots = 1`

## Result

`Phase 7` is verified complete for the current cut-over scope. Migrated `SYSTEM` runtime authority is SQL-only and fail-closed, while retained filesystem code is no longer part of active shared-runtime datum/audit authority.
