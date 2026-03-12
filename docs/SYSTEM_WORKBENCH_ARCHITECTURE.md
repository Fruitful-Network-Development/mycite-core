# SYSTEM Workbench Architecture

## Scope

This document defines the SYSTEM page workbench composition only.

- route: `/portal/system`
- shell host: `portals/*/portal/ui/templates/base.html`
- SYSTEM consumer: `portals/*/portal/ui/templates/services/system.html`

## Locked Composition

Inside the existing IDE shell, SYSTEM uses:

1. left context sidebar (page-local navigation/scoping)
2. center anthology workbench (graph-first + focused datum editor)
3. right inspector drawer (investigation/context)

The center workbench must open directly to graph/editor workflow. Stacked explanatory cards above graph are intentionally removed from primary flow.

## Component Sources

- workbench template:
  - `portals/mycite-le_fnd/portal/ui/templates/tools/partials/data_tool_shell.html`
  - mirrored to TFF
- runtime behavior:
  - `portals/mycite-le_fnd/portal/ui/static/tools/data_tool.js`
  - mirrored to TFF
- styling:
  - `portals/mycite-le_fnd/portal/ui/static/portal.css`
  - mirrored to TFF

## Residual Limitation

Advanced NIMM control panes still use compatibility overlay behavior for some flows.
