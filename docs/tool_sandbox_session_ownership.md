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

## Shared session registry

Use **`get_tool_sandbox_session_manager(app)`** from `portals/_shared/portal/sandbox/session_registry.py` so **Data API routes** and **tools** (e.g. AGRO) share the same in-process `ToolSandboxSessionManager` (`app.config["MYCITE_TOOL_SANDBOX_SESSION_MANAGER"]`).

## Session lifecycle helpers

- **`ToolSandboxSession.refresh_canonical_snapshot(deps)`** — reloads canonical anthology rows and re-binds `consumes_anthology_datum_ids` into `loaded_anthology_refs` (staged rows preserved).
- **`ToolSandboxSessionManager.reopen_session(...)`** — same `session_id`, fresh load from disk/declaration (used when `POST .../tool_session/open` has `"reopen": true`).

## Public payload aliases

- **`staged_rows`** in `to_public_dict()` mirrors **`staged_anthology_rows`** keys (anthology-shaped staged rows).
- Stage API accepts **`staged_rows`** as an alias for **`anthology_rows`** on `POST .../stage`.

## Related docs

- `docs/portal_core_tool_sandbox_consolidation_audit.md` — audit, bypass list, follow-ups.
