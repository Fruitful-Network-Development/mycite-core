# Sandbox Engine (Shared Core)

## Purpose

`portals/_shared/portal/sandbox/` is the canonical shared-core layer for sandbox-managed resource logic that should not be scattered across flavor routes, tool packages, or UI templates.

This pass introduces first working ownership for:

- MSS form compile/decode/edit staging
- MSS compact-array decode/context payloads
- SAMRAS structure encode/decode/normalize/validation
- contact-card exposed resource value generation
- inherited resource context resolution (local + foreign)
- FND SAMRAS anthology migration helpers

Sandbox does **not** own the cross-scope inventory model. Canonical local/inherited inventories are index-backed under `data/resources/index.local.json` and `data/resources/index.inherited.json`.

## Service surface

Primary entrypoint: `SandboxEngine` in `portals/_shared/portal/sandbox/engine.py`.

Core models:

- `MSSResource`
- `MSSCompactArray`
- `SAMRASResource`
- `ExposedResourceValue`
- `InheritedResourceContext`
- `SandboxCompileResult`
- `SandboxStageResult`

SAMRAS model helpers:

- `decode_structure_payload`
- `encode_structure_payload`
- `decode_node_value`
- `encode_node_value`
- `normalize_descriptor`
- `validate_node_value`
- `ensure_resource_row`
- `ensure_resource_object`

## API routes

Shared routes are registered in `portals/_shared/portal/api/data_workspace.py`:

- `GET /portal/api/data/sandbox/resources`
- `GET /portal/api/data/sandbox/resources/<resource_id>`
- `POST /portal/api/data/sandbox/resources/<resource_id>/stage`
- `POST /portal/api/data/sandbox/resources/<resource_id>/save`
- `POST /portal/api/data/sandbox/resources/<resource_id>/compile`
- `POST /portal/api/data/sandbox/mss/compile`
- `POST /portal/api/data/sandbox/mss/decode`
- `POST /portal/api/data/sandbox/samras/upsert`
- `GET /portal/api/data/sandbox/samras/<resource_id>/decode`
- `POST /portal/api/data/sandbox/inherited/resolve`
- `POST /portal/api/data/sandbox/inherited/compile_txa`
- `POST /portal/api/data/sandbox/inherited/adapt_txa`
- `GET /portal/api/data/sandbox/exposed/contact_card`
- `POST /portal/api/data/sandbox/migrate/fnd_samras`

Resource index routes (outside sandbox ownership but adjacent to sandbox lifecycle):

- `GET /portal/api/data/resources/local`
- `GET /portal/api/data/resources/inherited`
- `POST /portal/api/data/resources/local/migrate_legacy_samras`
- `POST /portal/api/data/resources/inherited/refresh`
- `POST /portal/api/data/resources/inherited/refresh_source`
- `POST /portal/api/data/resources/inherited/disconnect_source`

`/sandbox/inherited/compile_txa` is a narrow shared-core compiler path for txa-only inherited context. It produces field-usable inherited refs and a provisional SAMRAS descriptor without materializing full foreign txa/msn paths locally.

## Anthology migration model (FND)

The migration helper (`migrate_fnd_samras_rows_to_sandbox`) extracts full txa/msn SAMRAS trees into isolated sandbox resource JSON files and removes those full trees from portal anthology ownership.

Current FND canonical resources:

- `txa.samras.5-0-1`
- `msn.samras.5-0-2`

No full `4-1-*` txa tree should remain in anthology after migration.

## MVP inherited-write boundary

For AGRO MVP, sandbox provides the txa source-of-truth path:

1. load isolated resource JSON
2. compile MSS form
3. publish stable resource value
4. adapt to inherited txa context (`adapt_txa`)

Downstream product/invoice writes consume this context through shared write preview/apply and do not materialize full txa trees locally.

## Plot-plan draft resources

Sandbox also owns AGRO plan-draft resources (`resource_kind = plot_plan`) created from parcel geometry workspace resolution.

Current AGRO draft routes:

- `POST /portal/tools/agro_erp/plan/grid_preview`
- `POST /portal/tools/agro_erp/plan/draft/save`
- `GET /portal/tools/agro_erp/plan/draft/load`

Draft policy:

- draft artifacts are sandbox JSON resources, not anthology semantic rows
- saved payload captures selected parcel, geometry snapshot/refs, grid spec, and overlay compile metadata
- draft lifecycle is `save -> load -> update` within sandbox resource ownership

## Runtime validation

From repo root (`/srv/repo/mycite-core`):

- `.venv/bin/python -m unittest tests/test_sandbox_engine.py`
- `.venv/bin/python -m unittest tests/test_data_write_pipeline_routes.py`

These suites cover sandbox service behavior, migration behavior, and route-level sandbox integration.
