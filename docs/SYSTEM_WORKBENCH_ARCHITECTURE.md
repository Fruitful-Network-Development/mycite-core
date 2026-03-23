# SYSTEM Workbench Architecture

## Scope

This document defines the unified `/portal/system` page after the anthology/resources split was removed.

## Canonical model

`SYSTEM` now exposes one canonical workbench:

- center: one layered anthology-style table surface for all canonical files
- left: the page-local **control panel** for context summary and compatible mediations
- right: the **Details** inspector for active NIMM directive content

Legacy `local_resources`, `inheritance`, `workbench=anthology`, and `workbench=resources` URLs remain compatibility entry points only. They all resolve back into the same unified SYSTEM workbench shell.

## Canonical files

The workbench always operates on the fixed canonical file set:

- `anthology.json`
- `samras-txa.json`
- `samras-msn.json`

Default attention is `anthology.json`.

## NIMM + AITAS behavior

- Top-left workbench controls are always the four NIMM directives:
  - `Navigate`
  - `Investigate`
  - `Mediate`
  - `Manipulate`
- The grayscale AITAS strip sits directly beneath those controls.
- `Navigate` owns file switching when the workbench is at file focus.
- `Mediate` is driven by compatible-tool discovery instead of hardcoded launch buttons.
- File focus keeps `Spacial = 1`.
- Datum focus moves to `Spacial = 2`.

## Mutation policy

- `anthology.json`: direct write through the anthology authority path
- `samras-txa.json` and `samras-msn.json`: staged write with explicit publish
- create/delete affordances appear only while `Manipulate` is active

## Primary implementation files

- `portals/_shared/runtime/flavors/*/portal/ui/templates/services/system.html`
- `portals/_shared/runtime/flavors/fnd/portal/ui/templates/tools/partials/data_tool_shell.html`
- `portals/_shared/runtime/flavors/fnd/portal/ui/static/tools/data_tool.js`
- `portals/_shared/portal/ui/static/system_shell_runtime.js`
- `portals/_shared/portal/api/data_workspace.py`
- `portals/_shared/portal/application/shell/runtime.py`
- `portals/_shared/portal/sandbox/resource_workbench.py`
