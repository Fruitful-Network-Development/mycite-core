# System page — module content contract

The **shell contract** (`docs/portal_shell_contract.md`) is fixed infrastructure. System **modules** only supply content into shell slots.

## Slots modules may fill

| Slot | Where | Purpose |
|------|--------|---------|
| **workspace_content** | `system.html` → center `{% block body %}` for the active tab | Primary work surface: data, editors, tables, graphs |
| **inspector_content** | `system.html` → `{% block inspector_content %}` (per tab) | Detail, branch context, forms scoped to selection |
| **toolbar_actions** | Inline in workspace (compact rows) or registered DOM hooks | Save, stage, compile, refresh — **no** duplicate section nav |
| **empty_state** | Short inline copy when nothing selected | Not permanent instructional chrome |
| **advanced_debug** | `<details class="data-tool__advanced">` or equivalent | Raw JSON, paths, MSS, migration, API dumps |

Modules **must not**: render shell page titles, duplicate left-nav sections, embed a second inspector column in the center, or reflow inspector UI into the workspace when the inspector closes.

## Module-specific rules

### Anthology Workbench
- **Truth:** canonical `anthology.json` via the shared engine — not a generic dashboard.
- **Center:** table-first; grouped/graph is an alternate **mode** of the same surface (mutually exclusive).
- **Inspector:** datum/profile/editor/investigation only; no raw debug payloads as primary content.

### Local Resources
- **Truth:** sandbox JSON files under `sandbox/resources/<resource_id>.json` (plus staging files), with structured views layered on the same body.
- **Center:** file identity (path + kind) + workspace/structured/raw/staged; **not** inventory-only.
- **Inspector:** SAMRAS branch/path/siblings/children/next slot/structural detail when SAMRAS-backed; otherwise compact resource notes.

### Inheritance
- **Truth:** inherited resource **manager** — grouped sources and selectable resources.
- **Center:** source list + resource list; default view is management, not raw index JSON.
- **Inspector:** selected resource summary + refresh/disconnect actions; raw API JSON only under advanced.

### SAMRAS editor (Workbench submode)
- **Truth:** shared `samras_workspace` view-model and APIs for **TXA, MSN,** and future SAMRAS-backed sandbox resources.
- **Center:** editable/navigable title table + path/children affordances; session staging until promote.
- **Inspector:** shared SAMRAS inspector panel (`systemInspectorPanelTxa` host) for path, siblings, children, next child, structural detail, staged previews.
- **Session staging:** Local Resources and the Data Tool SAMRAS workspace share the same `sessionStorage` key prefix (`mycite.data_tool.txa_staged.v1:` + `resource_id`) so staged rows appear in both surfaces for the same resource.

## Implementation map (FND)

- `portals/.../templates/services/system.html` — tab bodies + inspector roots
- `portals/.../templates/tools/partials/data_tool_shell.html` — anthology + SAMRAS submode workspace
- `portals/.../static/tools/data_tool.js` — anthology + SAMRAS sandbox client
- `portals/.../static/tools/local_resources_workbench.js` — Local Resources client
- `portals/.../static/tools/inheritance_workbench.js` — Inheritance client
- `portals/_shared/portal/api/data_workspace.py` — sandbox resource, `samras_workspace`, inherited inventory APIs
- `portals/_shared/portal/sandbox/resource_workbench.py` — structured view-models for resource bodies
- `portals/_shared/portal/sandbox/txa_sandbox_workspace.py` — shared `build_samras_workspace_view_model`

TFF mirrors the same templates/static where the System page is shipped.
