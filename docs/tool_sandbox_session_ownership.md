# Tool sandbox session — frozen ownership

`ToolSandboxSession` (`portals/_shared/portal/sandbox/tool_sandbox_session.py`) is the **runtime/session owner** for tool-local workspace behavior: load → stage → understand → **promote**. It is **not** a canonical store.

## Inside the session (owned here)

- Declared **resources** (loaded snapshots from the sandbox engine).
- Declared **anthology datum refs** (`consumes_anthology_datum_ids`) and their loaded snapshots.
- **Config-derived inputs** (`config_coordinate_paths`, `optional_sandbox_resource_id_paths`, plus optional `initial_context.tool_context`).
- **Staged** row/resource edits (working copies derived from loaded + staged deltas).
- **Understanding** (`understand_datums`) and **rule policy** summaries for the session slice.
- **Promotion targets** (last computed resource ids / anthology ids to persist).
- **Warnings** and **errors** for the session lifecycle.

## Outside the session (must NOT live here)

- **Contract authority** and MSS contract compilation ownership (unchanged; not moved into sandbox).
- **Anthology authority** for canonical edits: promotion uses **hooks** that delegate to flavor `workspace` (e.g. `update_anthology_profile`); the session does not own storage.
- **Direct tool-local persistence** (files, ad hoc stores): tools promote via `LocalResourceLifecycleService` + anthology hooks only.
- **Ad hoc route-local semantic logic**: routes stay thin; they call the session service and shared rule/lifecycle APIs.

## Layers

| Layer | Role |
|--------|------|
| `ToolSandboxDeclaration` | Intent / contract with the portal (`workspace_contract.py`). |
| `ToolSandboxSession` | Runtime staging + validation + promotion orchestration. |
| `LocalResourceLifecycleService` | Canonical path for persisting local/sandbox **resources**. |
| Flavor `workspace` | Anthology **authority** when anthology rows are promoted. |

## First client

**AGRO ERP** uses this stack for plot-plan draft save/load and loads optional txa/msn resource ids from config when present (`AGRO_ERP_SANDBOX_DECLARATION`).
