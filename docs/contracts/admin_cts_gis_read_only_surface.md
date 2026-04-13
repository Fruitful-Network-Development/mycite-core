# Admin CTS-GIS Read-Only Surface

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This document defines the current V2 wire contract for the admin CTS-GIS
read-only tool surface.

## Ownership

- shell legality, routing, and admin-band placement are owned by
  `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py`
- runtime composition is owned by
  `MyCiteV2/instances/_shared/runtime/admin_cts_gis_runtime.py`
- datum authority remains with the datum-document seam and datum-recognition
  layer
- client JS renders the server-composed projection; it does not decode datum or
  coordinate overlays on its own

## Registry And Entrypoint

- `tool_id`: `cts_gis`
- `tool_kind`: `general_tool`
- `slice_id`: `admin_band5.cts_gis_read_only_surface`
- `entrypoint_id`: `admin.cts_gis.read_only`
- request schema: `mycite.v2.admin.cts_gis.read_only.request.v1`
- surface schema: `mycite.v2.admin.cts_gis.read_only.surface.v1`
- workbench kind: `cts_gis_workbench`
- inspector kind: `cts_gis_summary`
- config gate: `tool_exposure.cts_gis.enabled`

## Compatibility Boundary

- live datum evidence may still come from `data/sandbox/maps/**`
- legacy `tool.maps.json` and `tool_id="maps"` sandbox documents are
  compatibility evidence only
- forward V2 shell/runtime ids must stay `cts_gis`

## Request Shape

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

## Surface Payload

The surface payload contains:

- `document_catalog`
- `selected_document`
- `selected_row`
- `map_projection`
- `rows`
- `diagnostic_summary`
- `lens_state`
- `warnings`

`map_projection.projection_state` may be:

- `projectable`
- `inspect_only`
- `no_authoritative_cts_gis_documents`

## Immediate implementation rule

- keep CTS-GIS under `Utilities`
- do not promote CTS-GIS into a root service
- do not reintroduce `Maps` as the canonical live V2 name
