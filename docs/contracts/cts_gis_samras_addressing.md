# CTS-GIS SAMRAS Addressing

## Status

Canonical

## Current Contract

CTS-GIS uses `msn-SAMRAS` magnitude as the only authority for tree shape.

Administrative node rows are label overlays only. They do not define structure, parentage, or child continuity.

## Source Precedence

CTS-GIS resolves SAMRAS structure in this order:

1. scan `data/payloads/cache/<corpus>.msn-administrative.json` for decodable `msn-SAMRAS` candidates
2. scan `data/sandbox/cts-gis/tool.<msn>.cts-gis.json` for decodable `msn-SAMRAS` candidates
3. use the highest-ranked decodable candidate
4. if no structure row decodes, attempt legacy reconstruction from `data/sandbox/cts-gis/sources/<corpus>.msn-administrative.json`
5. if a decodable authority yields poor namespace coverage versus administrative unique node bindings, CTS-GIS may override it with reconstructed authority from administrative rows

CTS-GIS resolves ASCII node titles from:

1. `data/sandbox/cts-gis/sources/<corpus>.msn-administrative.json`

## Magnitude Decode Logic

The SAMRAS magnitude is decoded procedurally:

1. Read unary `address_width_field`
2. Read unary `stop_count_width_field`
3. Read fixed-width `stop_count_field`
4. Read the `stop_address_array`
5. Slice the concatenated `value_stream`
6. Interpret the first value as root count
7. Interpret every remaining value as the child count for the next node in breadth-first order
8. Derive node addresses from ordinal child position

The governing reference for the structure datum is `0-0-5`.

The derived namespace is fail-closed only when no valid structure authority or reconstructible row set exists. Overlay rows do not become the governing source of parentage.

Coverage override rule:

- CTS-GIS compares the active decoded namespace to unique administrative node bindings
- when reconstruction materially reduces `node_outside_magnitude` drift, reconstructed authority is preferred
- this keeps directory navigation operational when an anchor/cache magnitude is decodable but semantically stale

## Address Denotation

Node addresses are ordinal, contiguous, and structural:

- roots must be `1..n`
- every child sequence under a parent must be contiguous from `1`
- breadth-first child counts define the full address namespace

Example lineage:

- `3`
- `3-2`
- `3-2-3`
- `3-2-3-17`
- `3-2-3-17-77`

In that example, `3` is the third root, `3-2` is its second child, `3-2-3` is that node's third child, and so on.

## CTS-GIS Overlay Correlation

After CTS-GIS decodes the namespace, it joins node rows from the administrative source:

- `rf.3-1-2` -> SAMRAS node id
- `rf.3-1-3` -> title babelette payload

Overlay rules:

- decode `rf.3-1-3` as ASCII only
- when ASCII decode fails, `title=""`
- do not fall back to row labels for title text
- keep nodes in the namespace even when no title overlay is available

## Directory Dropdown Payload

CTS-GIS projects structural navigation through `navigation_canvas`:

- `navigation_canvas.mode = "directory_dropdowns"`
- `navigation_canvas.source_authority = "samras_magnitude"`
- `navigation_canvas.decode_state`
- `navigation_canvas.diagnostics`
- `navigation_canvas.dropdowns`
- `navigation_canvas.active_path`

`decode_state` is one of:

- `ready`
- `blocked_invalid_magnitude`

Each dropdown carries:

- `depth`
- `parent_node_id`
- `selected_node_id`
- `options`

Each option carries:

- `node_id`
- `title`
- `display_label`
- `selected`
- `shell_request`

Display rules:

- root labels render as `1 NEG` through `8 SWG`
- deeper labels render as `<node_id> <ascii_title>`
- when `title=""`, the visible label falls back to the bare `node_id`
- table/title rendering may use `node_id` fallback even when the underlying `title` field is empty

## Selection Normalization

CTS-GIS keeps SAMRAS navigation tool-local.

- when no attention node can be resolved yet, CTS-GIS may still carry the default token `intention_rule_id=descendants_depth_1_or_2`
- once CTS-GIS resolves an attention node and the request does not explicitly widen intention, the CTS-GIS service normalizes intention to `self`
- once a node-focused attention exists, widened scope round-trips as `self`, `<attention_node_id>-0`, `<attention_node_id>-0-0`, or `branch:<node_id>`
- the portal runtime transports the normalized tool-state envelope, but it does not invent the CTS-GIS intention default on its own
- this keeps Garland aligned to the currently selected structural node instead of a descendant render set

## Garland Coupling

Garland is driven by the currently selected SAMRAS node from `navigation_canvas.active_path`.

- `profile_projection` may materialize a blank but stateful current-profile view for a structurally valid selected node even when no matching profile source exists yet
- `geospatial_projection` remains empty until that selected node or its widened intention scope resolves projectable HOPS geometry
- node-focused widened intention keeps the selected node as Garland's active profile while geospatial overlays may combine multiple in-scope projectable profile source documents
- explicit source-document selection anchors row/detail evidence, and node/intention navigation preserves that pin unless the user explicitly switches source document
- if a node-specific profile source document exists, CTS-GIS may still prefer the profile source whose filename suffix matches the selected node id for the focused document view
- when a profile document carries `reference_geojson`, fallback geometry is allowed when HOPS decode cannot produce projectable coordinates for the row/profile or when semantic guardrails classify decode-valid geometry as implausible for the active node envelope; parity warnings alone do not switch geometry authority
- when blocked, CTS-GIS renders diagnostics and leaves Garland empty until a valid structural selection becomes possible

See `docs/contracts/cts_gis_garland_projection_lens.md` for bounds/focus and lens rendering rules.
See `docs/contracts/cts_gis_reference_promotion_and_profile_repair.md` for the
required source-repair workflow that updates profile documents bound to SAMRAS nodes.

## Diagnostics

CTS-GIS blocks navigation only when no valid SAMRAS structure can be recovered.

Secondary overlay problems remain visible as diagnostics without blocking bare node-id navigation:

- duplicate node-row bindings
- node rows outside the resolved namespace
- undecodable ASCII title payloads
- reconstructed authority override events when drifted decodable magnitudes are replaced
