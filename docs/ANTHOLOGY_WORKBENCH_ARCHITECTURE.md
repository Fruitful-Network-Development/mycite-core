# Anthology Workbench Architecture

## Purpose

SYSTEM Data surface is an anthology-authoritative workbench where graph navigation is primary and datum editing is synchronized in the same surface.

## Composition

Template:

- `portals/_shared/runtime/flavors/fnd/portal/ui/templates/tools/partials/data_tool_shell.html`

Mirrored to TFF.

Workbench regions:

1. graph-first pane (primary navigation surface)
2. focused datum editor pane (same workbench grid)
3. layer/value-group row explorer (context list)
4. right inspector drawer for investigation context

The pre-graph stacked explanatory cards were removed from central flow so the graph/editor workspace is immediately dominant.

## Interaction Model

- single click graph node: focus datum and sync editor
- double click graph node: investigate datum and open inspector
- selecting anthology row: sync graph focus + load datum editor
- save in datum editor: persist to anthology profile update route and refresh graph/table/editor state

## Engine/API Binding

Core routes used:

- `GET /portal/api/data/anthology/table`
- `GET /portal/api/data/anthology/graph`
- `GET /portal/api/data/anthology/profile/<row_id>`
- `POST /portal/api/data/anthology/profile/update`
- `POST /portal/api/data/directive`

State remains engine-driven (NIMM/AITAS), UI remains a consumer.

## Inspector Usage

Investigation updates the right inspector (`PortalInspector`) with abstraction path and state context. Main editing remains in the center workbench.

## Current Limitation

Advanced NIMM controls still include overlay compatibility paths; they are not yet fully re-mounted as first-class inspector tabs.
