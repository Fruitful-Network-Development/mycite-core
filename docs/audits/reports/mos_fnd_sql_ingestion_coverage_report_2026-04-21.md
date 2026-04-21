# MOS FND SQL Ingestion Coverage Report

Date: 2026-04-21

Doc type: `audit`  
Normativity: `supporting`  
Lifecycle: `completed`  
Last reviewed: `2026-04-21`

## Purpose

Record the final applied FND ingestion counts for the MOS SQL authority database and confirm that no authoritative rows or shared directive imports were left untracked during closure.

## Ingestion Summary

- `tenant_id`: `fnd`
- `tenant_domain`: `fruitfulnetworkdevelopment.com`
- `mode`: `apply`
- `authority_db_file`: `/srv/repo/mycite-core/deployed/fnd/private/mos_authority.sqlite3`
- `authoritative_documents`: `409`
- `authoritative_rows`: `3133`
- `supporting_anchor_rows`: `25215`
- `supporting_anchor_context_files`: `3`
- `derived_materialization_files`: `12`
- `explicit_exception_files`: `5`
- `untracked_authoritative_rows`: `0`
- `missing_directive_imports`: `0`

## Inventory

- `authoritative_import`: `409`
- `supporting_anchor_context`: `3`
- `derived_materialization`: `12`
- `explicit_exception`: `5`

## Directive Context

- `manifest_supplied`: `False`
- `snapshot_imported`: `0`
- `event_imported`: `0`
- note: No canonical shared directive overlays were imported because no explicit migration manifest was supplied.

## SQL Verification

- `document_semantics_count`: `409`
- `row_semantics_count`: `3133`
- `authoritative_catalog_snapshots`: `1`
- `system_workbench_snapshots`: `1`
- `publication_summary_snapshots`: `1`
- `portal_authority_count`: `1`
- `directive_snapshot_count`: `0`
- `directive_event_count`: `0`

## Coverage Assertions

1. Every authoritative document counted in the FND import is present in SQL document semantics.
2. Every authoritative datum row counted in the FND import is present in SQL row semantics.
3. No authoritative row remains untracked or exception-listed without rationale.
4. No shared directive snapshots or events are missing, because no manifest was supplied and no imports were expected.

## Coverage Gate

- `status`: `passed`
- rule: Every datum row must be present in SQL semantics or listed in the exception manifest with a reason.

## External Retained Scope

- `fnd/public`: host_bound_or_public_asset
- `fnd/build.json`: host_bound_or_public_asset
- `fnd/private/admin_runtime`: retained_private_scope_without_dedicated_port
- `fnd/private/contracts`: retained_private_scope_without_dedicated_port
- `fnd/private/daemon_state`: retained_private_scope_without_dedicated_port
- `fnd/private/network`: retained_private_scope_without_dedicated_port
- `fnd/private/progeny`: retained_private_scope_without_dedicated_port
- `fnd/private/utilities`: retained_private_scope_without_dedicated_port

## Result

FND ingestion coverage is complete for closure. The SQL authority database contains all `409` authoritative documents and `3133` authoritative datum rows, the supporting anchor total is `25215`, and there are `0` untracked authoritative rows plus `0` missing directive imports.
