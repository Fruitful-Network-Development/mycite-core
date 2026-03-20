# System page UI composition (workbench-first)

**Shell ownership** is defined in [`portal_shell_contract.md`](portal_shell_contract.md) (menu, left nav, center workspace, right inspector). **Module content contracts** are in [`module_system_contract.md`](module_system_contract.md). This document complements both with composition notes.

## Goals

The **System** area should read as a **workbench** (selection → workspace → inspector), not as stacked debug/report panels. Raw JSON, route blobs, schema strings, and storage-path notes remain available only as **secondary / advanced** surfaces.

## Layout model (frozen)

| Region | Responsibility |
|--------|----------------|
| **Left context sidebar** (`dtSystemContext` on System) | Navigation is in the IDE shell; this pane holds **search / select-mode** and other compact scope controls. |
| **Center** | Primary **workspace**: anthology surface or resources-table surface (query-state), local resource workspace tab, inheritance resource list. |
| **Right** | **Inspector**: datum editor + investigation embed (anthology), SAMRAS branch/structural inspector (sandbox), resource SAMRAS sidebar (local resources), inherited resource detail + sync actions (inheritance). |

## Anthology workbench (`data_tool_shell.html` + `data_tool.js`)

- **Truth:** UI for canonical **`anthology.json`** through the shared engine (not a generic dashboard).
- **Center column**: `dtWorkbenchGrid` — **table** is the default primary surface; **graph** is an alternate mode (mutually exclusive via `data-layout-mode` + CSS).
- **Graph tuning** (context, depth, focus, zoom) lives under **Advanced: Graph controls** (`<details>`).
- **Inspector (shell)**: `#dtAnthologyInspectorBody` + `#dtAnthologyInvMount` — datum editor / investigation; NIMM opened from a compact **Advanced** control.
- **Left `dtSystemContext`**: search / select-mode only.

## Resource workbench baseline (`workbench=resources`)

- **Switching** is query-state based from the left sidebar context links: `?tab=workbench&workbench=resources|anthology`.
- **No in-body mode tabs**: Anthology/SAMRAS navigation rows are removed from the center surface.
- **Center (resources)**: table-first datum surface from `GET /portal/api/data/system/resource_workbench`.
- **Canonical files (fixed for this pass)**: `anthology.json`, `samras-txa.json`, `samras-msn.json`.
- **Inspector (resources)**: selected row detail mounted in `#systemInspectorPanelResources`.

## Local Resources (`system.html` + `local_resources_workbench.js`)

- **Truth:** each selection maps to a **sandbox JSON file** `sandbox/resources/<resource_id>.json` (plus optional staging); the center makes that explicit (path line + file card).
- **Left**: merged sandbox + local index list; first sandbox file **auto-selects** on refresh when nothing is selected.
- Tab order (default **Workspace**):

1. **Workspace** — non-SAMRAS: compact summary; **SAMRAS-backed**: shared title table + path/children + session staging + promote (mirrors workbench SAMRAS APIs).  
2. **Structured** — anthology-shaped + `rows_by_address` tables.  
3. **Raw JSON** — full document editor.  
4. **Staged** — on-disk staging snapshot when present.

- **Inspector**: full SAMRAS branch inspector (path, siblings, children, next slot, structural detail) when applicable.

Advanced index/MSS/migration blocks stay under **Advanced: index JSON, MSS, migration**.

## Inheritance (`system.html` + `inheritance_workbench.js`)

- **Truth:** inherited resource **manager** (not a JSON dump by default).
- **Left**: sources from `GET /portal/api/data/resources/inherited` → `grouped_by_source`.  
- **Center**: resources for the selected source + **selected summary** card.  
- **Right**: selected resource detail + **Refresh this resource**; bulk source/contract actions under **Source & contract actions**; **last API JSON** under **Advanced**.  
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
