# MOS FND SQL Ingestion Report

- `tenant_id`: `fnd`
- `tenant_domain`: `fruitfulnetworkdevelopment.com`
- `mode`: `dry_run`
- `authority_db_file`: `/srv/repo/mycite-core/deployed/fnd/private/mos_authority.sqlite3`

## Inventory

- `authoritative_import`: 409
- `supporting_anchor_context`: 3
- `derived_materialization`: 12
- `explicit_exception`: 5

## Import Summary

- `document_count`: 409
- `row_count`: 3133
- `anchor_row_count`: 25215
- `supporting_anchor_context_count`: 3
- `derived_materialization_count`: 12
- `explicit_exception_count`: 5

## Directive Context

- `manifest_supplied`: False
- `snapshot_imported`: 0
- `event_imported`: 0
- note: No canonical shared directive overlays were imported because no apply step was requested.

## SQL Verification


## Coverage Gate

- `status`: dry_run
- rule: not_evaluated

## External Retained Scope

- `fnd/public`: host_bound_or_public_asset
- `fnd/build.json`: host_bound_or_public_asset
- `fnd/private/admin_runtime`: retained_private_scope_without_dedicated_port
- `fnd/private/contracts`: retained_private_scope_without_dedicated_port
- `fnd/private/daemon_state`: retained_private_scope_without_dedicated_port
- `fnd/private/network`: retained_private_scope_without_dedicated_port
- `fnd/private/progeny`: retained_private_scope_without_dedicated_port
- `fnd/private/utilities`: retained_private_scope_without_dedicated_port

## Failures

- none
