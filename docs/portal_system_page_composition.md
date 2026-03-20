# System page UI composition (workbench-first)

## Goals

The **System** area should read as a **workbench** (selection → workspace → inspector), not as stacked debug/report panels. Raw JSON, route blobs, schema strings, and storage-path notes remain available only as **secondary / advanced** surfaces.

## Layout model (frozen)

| Region | Responsibility |
|--------|----------------|
| **Left context sidebar** (`dtSystemContext` on System) | Navigation is in the IDE shell; this pane holds **search / select-mode** and other compact scope controls. |
| **Center** | Primary **workspace**: anthology grouped graph, SAMRAS sandbox structure + title table, local resource workspace tab, inheritance resource list. |
| **Right** | **Inspector**: datum editor + investigation embed (anthology), SAMRAS branch/structural inspector (sandbox), resource SAMRAS sidebar (local resources), inherited resource detail + sync actions (inheritance). |

## Anthology workbench (`data_tool_shell.html` + `data_tool.js`)

- **Center column**: `dtWorkbenchGrid` — in **grouped** mode the graph is the dominant row; the anthology table is a **context** band below (CSS `grid-template-rows`).
- **Graph tuning** (context, depth, focus, zoom) is folded under **“Graph focus, depth, and zoom”** (`<details>`).
- **Right column**: `#dtAnthologyInspector` with `#dtAnthologyInspectorBody` (datum editor + icon block) and `#dtAnthologyInvMount` (embedded investigation list; raw payload under **Advanced**).
- **Default layout mode** in markup: **grouped**; table-only remains available.
- **Left `dtSystemContext`**: no longer receives the full datum editor when the inspector column exists — it stays search/select-mode oriented.

## SAMRAS resource sandbox (Data Tool workspace tab)

- **Center** uses `data-tool__txaWorkspaceStack`: structure path/children **above** the title table so the workspace is one continuous surface.
- **Inspector** (`data-tool__txaBranchAside`): path segments are **clickable buttons** with depth index (shared pattern for TXA/MSN and future SAMRAS resources).

## Local Resources (`system.html` + `local_resources_workbench.js`)

Tab order (default **Workspace**):

1. **Workspace** — summary chips (understanding, row counts, staged flag) + guidance; not raw JSON.  
2. **Structured** — tables / grouped rows.  
3. **Raw JSON** — full document editor; storage path note under **Advanced**.  
4. **Staged** — readonly snapshot when present.

Advanced index/MSS blocks unchanged under **Advanced: index JSON, MSS, migration**.

## Inheritance (`system.html` + `inheritance_workbench.js`)

- **Left**: sources from `GET /portal/api/data/resources/inherited` → `grouped_by_source` (no backend change).  
- **Center**: resources for the selected source.  
- **Right**: selected resource fields + refresh/disconnect controls; **last API JSON** under **Advanced**.  
- **Full index JSON** under **Advanced: raw inherited index JSON**.

## Styling

Primary rules live in **`fnd/portal/ui/static/portal.css`** (`.data-tool__workbenchWithInspector`, grouped grid rows, TXA workspace stack, `.inh-workbench__*`, `.lr-workbench__workspace*`).

## Tests

- `tests/test_system_page_composition.py` — template markers + `grouped_by_source` API guard.  
- `tests/test_fnd_portal_shell_routes.py` — HTTP smoke for workbench / local_resources / inheritance markers when Flask is available.

## Follow-ups

- Further **de-chrome** anthology datum editor (row_id/identifier readouts → advanced).  
- Optional **inspector resize** / persisted column widths.  
- Align **TFF** styling if that flavor ships without `portal.css` (duplicate critical layout rules or share a thin common stylesheet).
