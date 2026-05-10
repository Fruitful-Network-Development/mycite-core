# Interface Panel Component Frame Contract

## Status

Canonical

## Purpose

Define the component frame model for the portal interface panel: how frames are structured,
how they are initialized, how they are frozen, and how they are re-engaged.

This contract is downstream of:

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/portal_panel_state_distinction.md`

This contract governs the interface panel's `interface_body.component_frames` payload shape
and the frontend rendering semantics in `v2_portal_interface_panel_host.js` and
`v2_portal_component_library.js`.

---

## Overview

The interface panel is composed of **component frames** — named payload slots each describing
a discrete renderable unit with its own type, initializer directive spec, content payload,
freeze state, and render key.

Frames are independent: a state-machine cycle that re-engages one frame does not affect
the frozen state of sibling frames on the same tab.

---

## Component Frame Schema

```json
{
  "frame_id": "<string>",
  "component_type": "<component_group | profile | geospatial_projection | characteristic_set | listing | chronology_matrix>",
  "label": "<human-readable label, optional>",
  "initializer": {
    "verb": "mediate",
    "target_authority": "<string>",
    "datum_address": "<datum address, optional>",
    "intent": "<string>",
    "parent_frame_id": "<string, optional — for child frames>"
  },
  "payload": { /* type-specific payload object */ },
  "frozen": true,
  "render_key": "<string — determines re-render eligibility>"
}
```

### Fields

- **frame_id** — Unique identifier within the containing surface. Used by the frontend registry
  and by engagement actions. Stable across state-machine cycles for the same logical frame.

- **component_type** — Determines which renderer handles this frame. See Component Types below.

- **label** — Optional human-readable label shown in the frame header.

- **initializer** — The declarative NIMM directive spec that produced (or can reproduce) this
  frame's payload. The server runs this directive during frame construction. The client re-fires
  it on engagement. Always `verb: "mediate"` for interface panel frames.

- **payload** — Type-specific content payload. Shape is determined by component_type.

- **frozen** — When `true`, the frontend treats this frame as frozen: if the registry already
  holds a rendered state with a matching `render_key`, the cached DOM is reused without
  calling the renderer again. When `false`, always re-render.
  **Override rule:** A changed `render_key` overrides `frozen=true`. The frozen flag
  prevents re-render ONLY when the incoming `render_key` matches the registry entry.
  A mismatched `render_key` always triggers re-render, regardless of the frozen flag.
  This means attention-node changes (which change the render_key) automatically
  invalidate cached frames even when they are marked frozen.

- **render_key** — A deterministic string derived from the frame's content identity.
  Formula: `"<attention_node_id>::<component_type>::<lens_key>"` where `lens_key` is
  derived from the active selected node id (stable within a session for the same
  attention/intention context). Example: `"3-2-3-17::profile::3-2-3-17"`.
  The server computes this; the client treats it as opaque. A changed render_key
  always causes re-render regardless of the frozen flag.

---

## Component Types

### `component_group`

Represents a named composition of child component frames. A group is used when one
interface tab is a reusable layout rather than a single payload, such as the CTS-GIS
Garland administrative/voter/election composition.

```json
{
  "label": "<group label>",
  "layout": "<garland_wireframe | stack | grid, optional>",
  "layout_slot": "<optional parent slot>",
  "children": [
    { /* nested component frame */ }
  ]
}
```

- `children[]` carries complete component frames and each child keeps its own initializer,
  frozen state, and render key.
- Empty-shell child frames are valid. They must carry their expected fields plus an
  `empty_message` so the renderer can display a stable frame without claiming source data exists.

### `profile`

Represents an administrative entity or subject profile.

```json
{
  "label": "<entity name>",
  "msn_id": "<msn node id, e.g. 3-2-3-17>",
  "variant": "<administrative_node | precinct | voter | generic, optional>",
  "layout_slot": "<optional group layout slot>",
  "fields": [
    { "label": "Name", "value": "<string>" },
    { "label": "MSN ID", "value": "<string>" },
    { "label": "Feature Count", "value": "<string>" },
    { "label": "Child Count", "value": "<string>" }
  ],
  "field_groups": [
    { "label": "<group label>", "fields": [{ "label": "<string>", "value": "<string>" }] }
  ],
  "collections": [
    { "label": "<collection label>", "items": [{ "label": "<string>", "value": "<string>" }] }
  ],
  "children": [
    { /* nested component frame, optional */ }
  ],
  "subject_slot": { /* nested component frame, optional */ },

  "hierarchy": [
    { "label": "<string>", "node_id": "<string>", "selected": false, "detail": "<optional>" }
  ],
  "district_overlay_toggle": {
    "enabled": false,
    "time_token": "<string>",
    "timeframe_match": false,
    "overlay_active": false,
    "action": { /* shell action, dispatched on toggle click */ },
    "shell_request": { "tool_state": {} }
  },
  "district_precinct_collections": [
    {
      "precinct_count": 0,
      "precinct_count_known": false,
      "member_labels": [],
      "member_node_ids": [],
      "summary_state": "<string>",
      "overlay_active": false
    }
  ],
  "summary_rows": [
    { "label": "<string>", "value": "<string>" }
  ],
  "warnings": [],
  "empty_message": "<string>"
}
```

- `hierarchy[]` provides the ancestor lineage chain for navigation stepping.
- `district_overlay_toggle` drives the precinct overlay toggle button. When `shell_request.tool_state`
  or `action` is present the button is interactive; otherwise it is inert.
- `district_precinct_collections[]` lists precinct cluster cards under the overlay section.
- `summary_rows[]` carries additional profile metadata rows (supporting doc, projection doc, etc.).
- `subject_slot` is an optional nested component frame rendered in the "subject" area of the
  profile component. Typically a `geospatial_projection` or `characteristic_set` frame.
- `field_groups[]` and `collections[]` are additive shell fields for profile variants that need
  grouped administrative, precinct, voter, ballot, or district-list metadata.
- `children[]` is for additional nested frames that do not semantically belong in the subject slot.
- The profile frame is resolved **before** its subject_slot: the server computes profile data
  first (by mediating on the anchor datum), then populates subject_slot from the profile result.
- The `subject_slot` frame carries the same component frame schema fields. Its `initializer`
  carries `parent_frame_id` identifying which parent frame's output feeds it. Its `render_key`
  uses the same formula: `"<attention_node_id>::<component_type>::<lens_key>"`.

```json
{
  "frame_id": "administrative_profile__geospatial",
  "component_type": "geospatial_projection",
  "initializer": {
    "verb": "mediate",
    "target_authority": "cts_gis",
    "intent": "resolve_geospatial_for_profile",
    "parent_frame_id": "administrative_profile"
  },
  "payload": { /* geospatial_projection payload */ },
  "frozen": true,
  "render_key": "3-2-3-17::geospatial_projection::3-2-3-17"
}
```

### `geospatial_projection`

Represents a spatial map projection. Full payload shape:

```json
{
  "projection_state": "<inspect_only | projectable | projectable_degraded | projectable_fallback>",
  "feature_collection": { "type": "FeatureCollection", "features": [] },
  "collection_bounds": [min_lon, min_lat, max_lon, max_lat],
  "focus_bounds": [min_lon, min_lat, max_lon, max_lat],
  "selected_feature_explicit": false,
  "overlay_layers": [
    { "layer_id": "<string>", "label": "<string>", "visible": false, "action": {} }
  ],
  "lens_state": {},

  "projection_source": "<none | HOPS | fallback>",
  "projection_health": { "state": "<empty | ok | degraded | fallback>", "reason_codes": [] },
  "fallback_reason_codes": [],
  "decode_summary": {
    "reference_binding_count": 0,
    "decoded_coordinate_count": 0,
    "failed_token_count": 0
  },
  "warnings": [],

  "features": [
    {
      "feature_id": "<string>",
      "label": "<string>",
      "node_id": "<string>",
      "geometry_type": "<Polygon | MultiPolygon | Point>",
      "selected": false,
      "detail": "<string, optional>"
    }
  ],
  "feature_count": 0,
  "render_feature_count": 0,
  "render_row_count": 0,

  "selected_feature_id": "<string>",
  "selected_feature_geometry_type": "<string>",
  "selected_feature_bounds": [min_lon, min_lat, max_lon, max_lat],

  "empty_message": "<string>",
  "supporting_document_name": "<string>",
  "projection_document_name": "<string>"
}
```

- This frame is populated retroactively from the parent profile frame's resolved geometry data.
- The `initializer.parent_frame_id` identifies which profile frame's output feeds this frame.
- `features[]` drives the feature list UI (click to select, highlight on map).
- `decode_summary` and `projection_health` are diagnostic fields for render status display.
- `selected_feature_id/bounds` track the currently highlighted feature.
- `empty_message` is shown when `projection_state = inspect_only` or `feature_count = 0`.

### `characteristic_set`

Represents a labeled collection of characteristic sub-items for a profile.

```json
{
  "label": "<set label>",
  "items": [
    { "label": "<characteristic name>", "value": "<string>", "detail": "<string, optional>" }
  ]
}
```

### `listing`

Represents a reusable ledger/table/list frame, including empty shells for data sources that are
not implemented yet.

```json
{
  "label": "<listing label>",
  "layout_slot": "<optional group layout slot>",
  "source_kind": "<administrative_log | voter_log | generic>",
  "columns": [
    { "key": "<column key>", "label": "<column label>" }
  ],
  "rows": [
    { "<column key>": "<value>" }
  ],
  "empty_message": "<string>"
}
```

### `chronology_matrix`

Represents chronological activity across labeled rows and time columns.

```json
{
  "label": "<matrix label>",
  "layout_slot": "<optional group layout slot>",
  "row_headers": [
    { "key": "<row key>", "label": "<row label>" }
  ],
  "column_headers": ["2012", "2013"],
  "events": [
    { "row_key": "<row key>", "column_key": "<year>", "value": "<marker>" }
  ],
  "empty_message": "<string>"
}
```

---

## Tab-Level Initializer

Each tab entry in `interface_body.tabs[]` may carry an `initializer` field:

```json
{
  "id": "garland",
  "label": "Garland",
  "initializer": {
    "verb": "mediate",
    "target_authority": "cts_gis",
    "datum_address": "1-1-2"
  }
}
```

**Tab-level vs frame-level initializer distinction:**

- **Tab-level initializer** fires when the tab is first activated (tab click or surface load
  with this tab active). It is **declarative metadata** documenting the mediation context
  the tab was designed to operate in. The server uses it to establish the frame payloads
  during surface build. The client does not fire the tab-level initializer independently.
- **Frame-level initializer** fires on **engagement** (user clicks the engage button on a
  specific frame). The client fires it as a tool action; the server re-runs the mediation
  for that specific frame and returns a refreshed payload.
- Frames initialize from their **own** initializer field, not from the tab's. The tab
  initializer is the context; the frame initializer is the re-engagement directive.

The tab initializer does NOT change the AITAS spatial value — see
`docs/contracts/portal_panel_state_distinction.md`.

---

## Parent-Child Initialization Order

When a component frame has a `subject_slot`, initialization is ordered:

1. The server resolves the **parent** frame first (e.g., profile via mediate on `1-1-2`).
2. The server uses the parent's resolved output to populate the **child** frame in `subject_slot`
   (e.g., geospatial projection from the profile's geometry data).
3. The client renders the parent frame, then renders the subject_slot frame within it.

This ordering is enforced server-side by the nesting structure. The client does not need to
sequence requests — the entire frame tree is pre-resolved in one server response.

---

## Frontend Freeze Semantics

The `ComponentFrameRegistry` in `v2_portal_interface_panel_host.js` maintains:

```
frame_id → { html: <rendered string>, render_key: <string> }
```

On each surface render:

1. For each frame in `interface_body.component_frames`:
   - If `frozen == true` and `registry[frame_id].render_key == frame.render_key`:
     - Use `registry[frame_id].html` (no re-render).
   - Else:
     - Call `PortalComponentLibrary.renderComponentFrame(frame)` → `html`.
     - Store in registry: `{ html, render_key: frame.render_key }`.
     - Insert `html` into the DOM.

2. Panel toggle (interface → workbench → interface) does not clear the registry.
   Frames are preserved across panel switches.

3. Full page reload clears the registry (module-scope IIFE, not persisted to localStorage).

---

## Engagement

A frozen frame can be re-engaged by the user. Engagement:

1. Clears the frame's registry entry: `registry.clear(frame_id)`.
2. Fires a tool action shell request: `action_kind = "engage_component_frame"`,
   `action_payload = { frame_id }`. This uses the same tool action dispatch path as
   other CTS-GIS actions (e.g., `toggle_overlay`).
3. The server detects `engaged_frame_id` in `tool_state`, forces a fresh `render_key`
   for that frame (ensuring the client registry sees a mismatch and re-renders it),
   then clears `engaged_frame_id` from `tool_state` for the next cycle.
4. Client receives the full surface response; the re-engaged frame has a new `render_key`
   that does not match the cleared registry entry, so it re-renders. Sibling frames
   with unchanged `render_key` values remain frozen.

The engage button carries:
`data-engage-frame="<frame_id>"` and `data-engage-initializer="<initializer JSON>"`.

**Note:** The `component_engage` key is a deprecated placeholder; the wired mechanism
is `action_kind = "engage_component_frame"` via `dispatchToolAction`. See
`TASK-UI-ENGAGEMENT-WIRING-2026-05-09.yaml` for implementation details.

---

## Backwards Compatibility

The `component_frames` field is additive alongside the existing `garland_split_projection`
field in the CTS-GIS interface body. Frontend renderers check for `component_frames` presence;
if absent, they fall back to the `garland_split_projection` rendering path. This allows
incremental rollout and rollback.

---

## Non-Goals

- Component frames do not define their own routes or shell-level focus transitions.
- Frames do not replace the workbench panel's datum navigation — they are mediation outputs only.
- The component frame model does not manage NAVIGATE or MANIPULATE directives; those remain
  in the control panel and workbench layer.

---

## Directive Terminal Text Grammar

The directive terminal accepts free-form text in a canonical format. All parsing and
validation is performed by `parse_directive_text()` in
`MyCiteV2/packages/state_machine/nimm/directives.py`.

**Format:**

```
verb;target_authority:datum_address
```

**Examples:**

```
med;cts_gis:1-1-2       → mediate, re-engages administrative_node_profile
nav;cts_gis:3-2-3-17    → navigate, no automatic frame engagement
inv;cts_gis:1-1-1       → investigate, no automatic frame engagement
man;cts_gis:1-1-2       → manipulate, no automatic frame engagement
```

**Canonical verb aliases** (normalized by `normalize_nimm_verb()`):

| Alias | Canonical |
|-------|-----------|
| `nav` | `navigate` |
| `inv` | `investigate` |
| `med` | `mediate` |
| `man` | `manipulate` |

**Verb→frame engagement** is defined by `NIMM_VERB_FRAME_ENGAGEMENT` in
`MyCiteV2/packages/state_machine/nimm/mediate_handlers.py`. The map is the single
authoritative source for which frame a given verb re-engages — tool runtimes must not
hardcode this mapping inline.

**Format constant:** `NIMM_DIRECTIVE_TEXT_FORMAT` in `nimm/directives.py` holds the
human-readable format string used in error messages throughout the system.
