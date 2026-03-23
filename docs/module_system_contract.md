# SYSTEM module contract

## Slots

| Slot | Purpose |
|------|---------|
| `workspace_content` | Unified layered SYSTEM workbench |
| `inspector_content` | File-level and datum-level Details content |
| `toolbar_actions` | Inline workbench actions such as refresh, create, delete, publish |
| `empty_state` | Compact no-selection or no-datum copy |

Modules must not reintroduce separate anthology/resources body tabs or a second inspector column in the center workspace.

## Unified SYSTEM rules

- Canonical file set:
  - `anthology.json`
  - `samras-txa.json`
  - `samras-msn.json`
- Default attention: `anthology.json`
- File switching happens through `Navigate`, not through SYSTEM view links.
- The control panel shows current context and compatible mediations.
- The Details panel is driven by the active NIMM directive and current AITAS state.

## Manipulate contract

- `anthology.json` uses the existing anthology mutation authority path.
- `samras-txa.json` and `samras-msn.json` use the canonical SYSTEM mutate/publish path.
- Create/delete affordances are visible only while `Manipulate` is active.

## Key files

- `portals/_shared/runtime/flavors/*/portal/ui/templates/services/system.html`
- `portals/_shared/runtime/flavors/fnd/portal/ui/static/tools/data_tool.js`
- `portals/_shared/portal/api/data_workspace.py`
