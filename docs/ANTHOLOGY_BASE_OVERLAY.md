# Anthology Base + Overlay Model

## Canonical ownership boundary

- `anthology-base.json` (repo root) is the canonical base registry for reserved/common datums.
- `compose/portals/state/<portal>/data/anthology.json` is the portal-local overlay.
- Runtime anthology authority remains local and file-backed; the merged anthology view is derived at load-time.

## Normalized datum object model

Shared normalization modules:

- `portals/_shared/portal/data_engine/anthology_schema.py`
- `portals/_shared/portal/data_engine/anthology_registry.py`
- `portals/_shared/portal/data_engine/anthology_overlay.py`

Each row normalizes to a canonical object with:

- `datum_id`
- `layer`
- `value_group`
- `iteration`
- `title`
- `icon_ref` (optional, sidecar-oriented)
- `row_kind` (`definition | tuple | selection | collection`)
- `definition` / `tuple_pairs`
- `source_scope` (`base` or `portal`)
- `row_payload` (pairs/reference/magnitude-compatible payload)

## Merge behavior

- Base rows load first from `anthology-base.json`.
- Portal overlay rows apply second.
- Deterministic ordering: `layer -> value_group -> iteration`.
- Overlay collisions on base IDs are allowed in compatibility mode and reported as warnings.
- `source_scope` is tracked per row in the merged view.

## Icon metadata policy

Icons remain sidecar metadata in `data/presentation/datum_icons.json`.

- Anthology rows remain semantic payload rows.
- Icon assignment/remapping stays in workspace/storage sidecar handlers.
- Do not move icon metadata into anthology row payloads.

## Migration model

Migration helper:

- `strip_base_duplicates_from_overlay(...)`
- `migrate_overlay_file(..., apply_changes=False|True)`

Purpose:

- Remove overlay rows that are exact duplicates of base rows.
- Preserve portal-specific rows and explicit local overrides.
- Support dry-run report before apply.

Route surface:

- `POST /portal/api/data/anthology/overlay/migration`
  - `{"apply": false}` for report only
  - `{"apply": true}` to rewrite local overlay file

## Compatibility notes

- Legacy raw compact anthology files continue to load.
- Contract/MSS compile paths and table/graph/profile views consume merged payloads.
- Existing runtime mutation paths still write compact anthology shape, now de-duplicated against base on persist.
