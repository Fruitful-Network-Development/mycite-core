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
- `POST /portal/api/data/sandbox/mss/compile`
- `POST /portal/api/data/sandbox/mss/decode`
- `POST /portal/api/data/sandbox/samras/upsert`
- `GET /portal/api/data/sandbox/samras/<resource_id>/decode`
- `POST /portal/api/data/sandbox/inherited/resolve`
- `GET /portal/api/data/sandbox/exposed/contact_card`
- `POST /portal/api/data/sandbox/migrate/fnd_samras`

## Anthology migration model (FND)

The migration helper (`migrate_fnd_samras_rows_to_sandbox`) converts full SAMRAS payload rows into sandbox-managed resource objects and rewrites anthology rows to compatibility pointers.

Current mapping:

- `5-0-1` -> `sandbox://samras/txa-samras`
- `5-0-2` -> `sandbox://samras/msn-samras`

This keeps higher-layer references stable while removing full SAMRAS payload ownership from ordinary anthology row magnitudes.

## Runtime validation

From repo root (`/srv/repo/mycite-core`):

- `.venv/bin/python -m unittest tests/test_sandbox_engine.py`
- `.venv/bin/python -m unittest tests/test_data_write_pipeline_routes.py`

These suites cover sandbox service behavior, migration behavior, and route-level sandbox integration.
