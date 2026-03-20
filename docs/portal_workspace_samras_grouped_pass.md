# Portal workspace consolidation — grouped workbench + SAMRAS sandbox (pass notes)

## Summary

This pass moves **anthology workbench graph** presentation to a **grouped / banded** layout (layer × value-group columns), removes the **radial** graph mode from the Data Tool, and retires **linear** as a user-facing layout name (legacy `linear`/`radial` API requests map to **grouped** with a warning).

It adds **shared composition** under `portals/_shared/portal/workbench/` and proves **MSN** parity for SAMRAS title promotion via `SandboxEngine`.

## Shared core

| Area | Location |
|------|-----------|
| Grouped anthology bundle (from `anthology_table_view`) | `_shared/portal/workbench/workbench_composition.py` → `build_grouped_workbench_bundle` |
| SAMRAS structural detail VM (generic sidebar / burst) | `_shared/portal/workbench/samras_structural_detail.py` → `build_samras_structural_detail_vm` |
| Staged title promotion | `_shared/portal/sandbox/samras_workspace_promotion.py` → `promote_staged_samras_title_entries` |

`Workspace._state_response` now includes `workbench_grouped` when composition succeeds.

`Workspace.anthology_graph_view` returns `grouped_bands` (layer → value-group columns → nodes) and reports `layout.mode=grouped` with `supported_modes: ["grouped"]`.

## Flavor deduplication

`portals/_shared/runtime/flavors/fnd/data/engine/workspace.py` is a **thin loader** of the TFF `Workspace` implementation so the large module is single-sourced.

## Data Tool (FND)

- Layout selector: **table** | **grouped** (linear/radial removed from UI).
- Graph edges use **quadratic SVG paths** (arc-like) instead of straight segments only.
- **SAMRAS resource sandbox** tab uses `POST /portal/api/data/sandbox/samras_workspace/view_model`.
- **Promote staged (sandbox)** calls `POST /portal/api/data/sandbox/resources/<id>/promote_staged_samras_titles`.
- Right rail adds **Structural detail (SAMRAS)** from `view_model.structural_detail`.

## API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/portal/api/data/sandbox/samras_workspace/view_model` | Generic SAMRAS workspace VM (TXA, MSN, …) |
| POST | `/portal/api/data/sandbox/resources/<resource_id>/promote_staged_samras_titles` | Persist staged title rows via `SandboxEngine` |
| GET | `/portal/api/data/anthology/graph` | Default `layout=grouped` |

`POST .../txa_workspace/view_model` remains for backward compatibility.

## Reverse-mutation workflow (implemented subset)

**Flow:** browser-staged title entries → **Promote staged** → `promote_staged_samras_title_entries` → `create_or_update_samras_resource` when `structure_payload` exists, else **`rows_by_address` merge + `save_resource`**.

**Deferred / boundary:** rows-only promotion does not yet mirror every guard in `POST .../save` (e.g. `evaluate_resource_payload_write` when a rows payload is extractable). When `extract_rows_payload_from_resource_body` applies to the merged body, promotion should run the same evaluation as the save route — follow-up if rule gates must block engine writes here too.

## Tests

- `tests/test_workbench_composition.py` — grouped bundle + structural detail VM
- `tests/test_samras_workspace_promotion.py` — MSN `rows_by_address` promote
- `tests/test_txa_sandbox_workspace.py` — `structural_detail` on `build_samras_workspace_view_model`

## References (visual direction only)

Grouped / arc metaphor: `arch_chart-*.png`, `vertical_burst_hierarchy-*.png` under the Cursor assets folder — used as **interaction/layout hints**, not pixel-perfect specs.
