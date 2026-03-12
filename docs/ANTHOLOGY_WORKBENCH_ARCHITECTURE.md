# Anthology Workbench Architecture

## Purpose

SYSTEM Data surface is a coordinated anthology workbench, not separate graph/table pages.

## Composition

Template:

- `portals/mycite-le_fnd/portal/ui/templates/tools/partials/data_tool_shell.html`

Mirrored to TFF.

Workbench regions:

1. graph pane (primary navigation surface)
2. datum editor pane (focused datum editing)
3. layered row explorer (context rows grouped by layer/value_group)
4. right inspector for investigation details

## Interaction Model

- single click graph node: focus datum (`inv summary`) and sync editor
- double click graph node: investigate datum (`inv abstraction_path`) and open inspector
- selecting anthology row: sync graph focus + load datum editor
- save in datum editor: persists through canonical anthology profile update route and refreshes graph/table

## Engine/API Binding

Core routes used:

- `GET /portal/api/data/anthology/table`
- `GET /portal/api/data/anthology/graph`
- `GET /portal/api/data/anthology/profile/<row_id>`
- `POST /portal/api/data/anthology/profile/update`
- `POST /portal/api/data/directive`

State remains engine-driven (NIMM/AITAS).

## Inspector Usage

Investigation and contextual detail use right inspector behavior (`PortalInspector`) rather than introducing a detached inline card column.

## Current Limitation

Advanced NIMM controls still have an overlay implementation path for compatibility; main workbench focus/investigation now centers on graph+editor synchronization.
