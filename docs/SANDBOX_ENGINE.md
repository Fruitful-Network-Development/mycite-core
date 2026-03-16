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

## Runtime validation

From repo root (`/srv/repo/mycite-core`):

- `.venv/bin/python -m unittest tests/test_sandbox_engine.py`
- `.venv/bin/python -m unittest tests/test_data_write_pipeline_routes.py`

These suites cover sandbox service behavior, migration behavior, and route-level sandbox integration.
