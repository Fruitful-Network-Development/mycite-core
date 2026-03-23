# TXA sandbox workspace UI pass (historical)

This document is historical context from the pre-hardening SAMRAS workspace. Current SAMRAS sandbox behavior is structure-aware and delegated through `portals/_shared/portal/samras/`; `rows_by_address` is now compatibility/support data, not the semantic owner.

## Phase 1 — Audit summary (current state)

### Available

- **Sandbox SAMRAS resource** shape: `rows_by_address` + `structure_payload` / `samras_structure` (`decode_resource_rows`, `SandboxEngine.decode_samras_resource`, `create_or_update_samras_resource`).
- **Node APIs**: inspect / set / create_child / delete / move (`/portal/api/data/sandbox/samras/<resource_id>/node/*`).
- **Data Tool shell**: anthology workbench layout; **workspace tab** added for **TXA sandbox (resource)** without removing anthology UI.
- **Client SAMRAS math** in `data_tool.js` (`samrasNextChildAddress`, etc.) for **anthology-backed** SAMRAS tables (`/portal/api/data/samras/*`).

### Gaps (before this pass)

- No HTML surface wired for sandbox-scoped TXA SAMRAS in `data_tool_shell.html` (SAMRAS controls in JS had no matching markup).
- No shared helper to assemble **title + address + branch context** for a **sandbox resource_id** with **honest staged** rows.

### This pass (implemented)

- **`txa_sandbox_workspace.py`**: pure view-model builders + `samras_next_child_address` aligned with Data Tool segment rules.
- **`POST /portal/api/data/sandbox/txa_workspace/view_model`**: returns `title_table_rows`, `branch_context`, `normalized_staged_entries`, `stage_warnings`.
- **UI**: second workspace tab **TXA sandbox (resource)** — title table, mini structure path + children, **right aside** (path list, siblings, children, next slot), **sessionStorage** staging (not persisted).

## Phase 7 — Follow-up: full reverse-update chain (explicit)

When implementing promotion, the server path must (in order, transactionally where possible):

1. **SAMRAS structure**: extend bitstring / `address_map` via `SandboxEngine.create_samras_child` (or equivalent) so the new node exists at the previewed address.
2. **Title isolate / collection rows**: create or update anthology (or compact) rows for the **title** datum and **txa_id** collection membership per product grammar (VG2 table-like), using **workspace** / `apply_write_preview` / rule evaluation — not ad hoc files.
3. **`rows_by_address`** on the resource: call `ensure_resource_row` semantics (or `create_or_update_samras_resource` with merged rows) so **names travel with the resource**.
4. **MSS / compile**: re-run `compile_isolated_mss_resource` or SAMRAS compile so published form includes titles.
5. **Tool sandbox session** (if used): **promote** staged entries through `LocalResourceLifecycleService` + declared hooks only.

Until then, **staged** rows remain **browser-local** and are labeled **staged** in the table.

## Files touched

- `portals/_shared/portal/sandbox/txa_sandbox_workspace.py` (new)
- `portals/_shared/portal/api/data_workspace.py` (route)
- `portals/_shared/portal/sandbox/__init__.py` (export)
- `portals/_shared/runtime/flavors/fnd/portal/ui/templates/tools/partials/data_tool_shell.html`
- `portals/_shared/runtime/flavors/fnd/portal/ui/static/tools/data_tool.js`
- `portals/_shared/runtime/flavors/fnd/portal/ui/static/portal.css`
- `tests/test_txa_sandbox_workspace.py` (new)
