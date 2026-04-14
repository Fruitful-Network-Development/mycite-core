# Admin CTS-GIS Read-Only Surface

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This document defines the current V2 wire contract for the admin CTS-GIS
read-only mediation surface.

## Ownership

- shell legality, routing, and admin-band placement are owned by
  `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py`
- runtime composition is owned by
  `MyCiteV2/instances/_shared/runtime/admin_cts_gis_runtime.py`
- CTS-GIS mediation and projection are owned by
  `MyCiteV2/packages/modules/cross_domain/cts_gis/service.py`
- datum authority remains with the datum-document seam and datum-recognition
  layer
- client JS renders the server-composed mediation/projection state; it does not
  decode HOPS or SAMRAS semantics on its own

## Registry And Entrypoint

- `tool_id`: `cts_gis`
- `tool_kind`: `general_tool`
- `slice_id`: `admin_band5.cts_gis_read_only_surface`
- `entrypoint_id`: `admin.cts_gis.read_only`
- request schema: `mycite.v2.admin.cts_gis.read_only.request.v1`
- surface schema: `mycite.v2.admin.cts_gis.read_only.surface.v1`
- workbench kind: `cts_gis_workbench`
- inspector kind: `cts_gis_interface_panel`
- config gate: `tool_exposure.cts_gis.enabled`

## Compatibility Boundary

- live datum evidence may still come from `data/sandbox/maps/**`
- legacy `tool.maps.json` and `tool_id="maps"` sandbox documents are
  compatibility evidence only
- forward V2 shell/runtime ids must stay `cts_gis`
- legacy `selected_document_id`, `selected_row_address`, and
  `selected_feature_id` request fields remain accepted only as a bridge into the
  mediation-state model

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
- `mediation_state`

`overlay_mode` must be `auto` or `raw_only`.

`mediation_state`, when present, contains:

- `attention_document_id`
- `attention_node_id`
- `intention_token`

Rules:

- `mediation_state` is the forward CTS-GIS request model
- the runtime may derive `mediation_state` from the legacy row/feature selectors
- `intention_token` is opaque to the client; valid options are issued by the
  runtime in the surface payload

## Surface Payload

The surface payload contains:

- `document_catalog`
- `selected_document`
- `attention_profile`
- `lineage`
- `children`
- `related_profiles`
- `render_set_summary`
- `selected_row`
- `map_projection`
- `rows`
- `diagnostic_summary`
- `lens_state`
- `mediation_state`
- `warnings`

`mediation_state` contains:

- `attention_document_id`
- `attention_node_id`
- `intention_token`
- `available_intentions`
- `selection_summary`

`map_projection.feature_collection.features[*].properties` carries:

- `samras_node_id`
- `profile_label`
- `title_display`
- `lineage`
- `parent_node_id`
- `diagnostic_states`
- `attention_member`

`map_projection.projection_state` may be:

- `projectable`
- `inspect_only`
- `no_authoritative_cts_gis_documents`

Both shell regions render from the same canonical `surface_payload`.
The interface panel owns operator mediation and the GeoJSON lens.
The workbench owns evidence, diagnostics, document switching, and expanded raw
inspection.

## Mediation And Projection Rules

- SAMRAS governs node/profile traversal and attention state
- HOPS governs coordinate decoding and derived spatial projection
- intra-document datum-address links may bridge profile rows to geometry rows
- the client must render only server-issued `available_intentions`
- the dominant interface panel renders the GeoJSON lens, attention shell,
  intention controls, lens toggles, and concise operator focus using the
  canonical `surface_payload`
- the background workbench renders document catalog, projected-feature tables,
  diagnostics, warnings, and raw datum evidence from that same payload
- CTS-GIS remains under `Utilities`; it is not promoted into a root service
- CTS-GIS uses the unified shell surface; it does not define a tool-owned shell
  model
