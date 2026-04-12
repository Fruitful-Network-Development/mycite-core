# Admin Maps Read-Only Surface

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This document defines the current V2 wire contract for the admin Maps read-only
tool surface. It is a runtime and shell contract, not a UX mockup.

## Ownership

- Shell legality, routing, and admin-band placement remain owned by
  `packages/state_machine/hanus_shell/admin_shell.py`.
- Runtime composition remains owned by
  `instances/_shared/runtime/admin_maps_runtime.py`.
- Datum authority remains owned by the authoritative datum-document seam and the
  datum-recognition layer. Maps does not introduce a second datum source.
- Client JS renders server-composed map and inspection payloads; it does not
  decode HOPS, SAMRAS, or title-babelette values on its own.

## Registry and entrypoint

- `tool_id`: `maps`
- `slice_id`: `admin_band5.maps_read_only_surface`
- `entrypoint_id`: `admin.maps.read_only`
- request schema: `mycite.v2.admin.maps.read_only.request.v1`
- surface schema: `mycite.v2.admin.maps.read_only.surface.v1`
- workbench kind: `maps_workbench`
- inspector kind: `maps_summary`
- config gate: `tool_exposure.maps.enabled`

## Request shape

Required fields:

- `schema`
- `tenant_scope`

Optional fields:

- `shell_chrome`
- `selected_document_id`
- `selected_row_address`
- `selected_feature_id`
- `overlay_mode`
- `raw_underlay_visible`

`overlay_mode` must be `auto` or `raw_only`.

## Surface payload

The runtime surface payload contains:

- `schema`
- `active_surface_id`
- `current_admin_band`
- `exposure_status`
- `read_write_posture`
- `document_catalog`
- `selected_document`
- `selected_row`
- `map_projection`
- `rows`
- `diagnostic_summary`
- `lens_state`
- `warnings`

## Projection contract

`map_projection` is server-composed and safe for direct rendering.

Required fields:

- `projection_state`
- `feature_count`
- `selected_feature`
- `feature_collection`

`projection_state` may be:

- `projectable`
- `inspect_only`
- `no_authoritative_maps_documents`

`feature_collection` uses a GeoJSON-like shape:

- `type: "FeatureCollection"`
- `features`
- `bounds`

## Datum and lens rules

- Raw datum rows remain present in `rows[*].raw`.
- Overlay values are presentation-only and do not replace raw datum truth.
- Illegal literals such as `HERE` remain visible as raw values and must stay
  attached to their diagnostics.
- HOPS projection may create point or polygon features only from valid
  HOPS-babelette coordinate bindings.
- Unresolved anchors, invalid coordinate tokens, and address irregularities stay
  in diagnostics and must not be silently plotted.

## Error posture

Renderable `200` surfaces are valid for:

- no authoritative maps documents
- authoritative maps documents with no projectable features
- mixed-validity documents with diagnostics

Envelope errors are reserved for:

- malformed request
- audience mismatch
- missing host data root
- `tool_not_exposed`
