# Anthology Graph Extraction Model

## Canonical Source

Graph extraction is anthology-authoritative and derived from anthology rows, not a separate mock graph model.

- API: `GET /portal/api/data/anthology/graph`
- engine: `portals/*/data/engine/workspace.py::anthology_graph_view`

## Node Derivation

Each anthology row emits one node with:

- `identifier`, `row_id`, `layer`, `value_group`, `iteration`
- `label`
- `pair_count`
- `pattern_kind` (`collection`, `typed_leaf`, `composite`)

## Edge Derivation

Edges are extracted from anthology references:

- `value_group == 0`: from `selection_references`
- other groups: from row `pairs[].reference`

Each edge includes:

- `source`, `target`, `reference`, `resolved`

## Focus / Context

The graph endpoint supports:

- `focus=<datum-id>`
- `context=local|global`
- `depth=<n>`
- `layout=linear|radial`

Local mode uses depth-limited neighborhood inclusion around focus.

## UI Semantics

UI renderer applies visual states from focus context:

- `focus` (active datum)
- `path` (lineage/abstraction path emphasis)
- `context` (direct neighboring context)
- `dim` (de-emphasized non-active context)

## Residual Limitation

Pattern classification currently uses row-shape heuristics and does not yet include richer typed-domain pattern registry overlays.
