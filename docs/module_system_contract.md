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

### Resource workbench (System workbench mode = resources)
- **Truth:** table-first explorer over canonical JSON files; backend still materializes `anthology.json`, `samras-txa.json`, `samras-msn.json`.
- **Center:** internal **file tabs** for **TXA + MSN only** inside the workbench card; rows come from `GET /portal/api/data/system/resource_workbench` (`resource_surface_file_keys`, flattened `rows`).
- **Left (task):** datum profile + **Navigate / Investigate / Mediate / Manipulate** (not file switches).
- **Inspector:** `systemInspectorPanelResources` — task + row driven panels; **Mediate** uses `samras_rows_by_address_by_file_key`.
- **Shell switching:** query-state only (`/portal/system?tab=workbench&workbench=resources|anthology`); Anthology remains a separate `workbench=anthology` surface.

## Implementation map (FND)

- `portals/.../templates/services/system.html` — tab bodies + inspector roots
- `portals/.../templates/tools/partials/data_tool_shell.html` — anthology workspace + resources-table workspace (query-state)
- `portals/.../static/tools/data_tool.js` — anthology + resources-table workbench client
- `portals/.../static/tools/local_resources_workbench.js` — Local Resources client
- `portals/.../static/tools/inheritance_workbench.js` — Inheritance client
- `portals/_shared/portal/api/data_workspace.py` — sandbox resource, `samras_workspace`, inherited inventory APIs
- `portals/_shared/portal/sandbox/resource_workbench.py` — structured view-models for resource bodies
- `portals/_shared/portal/sandbox/txa_sandbox_workspace.py` — shared `build_samras_workspace_view_model`

TFF mirrors the same templates/static where the System page is shipped.
