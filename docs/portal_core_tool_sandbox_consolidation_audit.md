# Portal core — tool sandbox / session consolidation audit

This memo satisfies Phases **1** and **15** of the tool sandbox consolidation request: current-state audit, what is shared, what duplicates, bypass risks, and follow-ups. It complements `docs/portal_core_sandbox_consolidation.md` and `docs/tool_sandbox_session_ownership.md`.

## What is already shared correctly

| Area | Location |
|------|-----------|
| Sandbox engine | `portals/_shared/portal/sandbox/engine.py` |
| **Tool sandbox session** (runtime staging + promote) | `portals/_shared/portal/sandbox/tool_sandbox_session.py` |
| **Session manager registry** (one manager per Flask app) | `portals/_shared/portal/sandbox/session_registry.py` → `get_tool_sandbox_session_manager(app)` |
| Local resource lifecycle | `portals/_shared/portal/sandbox/local_resource_lifecycle.py` |
| Tool declaration (intent) | `portals/_shared/portal/sandbox/workspace_contract.py` (`ToolSandboxDeclaration`, `AGRO_ERP_SANDBOX_DECLARATION`) |
| Inherited subscription service | `portals/_shared/portal/data_engine/inherited_contract_resources.py` |
| Rules / `RulePolicy` / write evaluation | `portals/_shared/portal/data_engine/rules/` |
| Generic tool session HTTP API | `register_data_routes` in `portals/_shared/portal/api/data_workspace.py` |
| TXA sandbox view-model (title table + branch preview) | `portals/_shared/portal/sandbox/txa_sandbox_workspace.py` |

## What still duplicates (acceptable for now)

| Area | Notes |
|------|--------|
| Flavor `workspace.py` (FND/TFF) | Large; anthology + NIMM authority — further extraction is incremental. |
| Flavor `app.py` | Registration glue; keep thin; move more to shared bootstrap over time. |
| `ToolSandboxRuntimeDeps` construction | AGRO builds deps locally; same shape as data API — could share a factory later. |

## What still bypasses sandbox / shared lifecycle (audit)

| Path | Status |
|------|--------|
| **AGRO** `plot_plan_draft_save` / `load` | **Patched**: uses `ToolSandboxSession` + `LocalResourceLifecycleService` via promote. |
| **AGRO** `_save_active_config_for_write` | **Intentional**: private portal config JSON, not anthology/sandbox row store. |
| **AGRO** MVP / `_sandbox_engine()` compile paths | **Remaining**: compile/adapt TXA still call engine directly where no unified “session promote” exists yet. |
| **Data Tool** / anthology commits | **By design**: anthology authority stays in flavor `workspace`, not sandbox session. |
| **NETWORK > Contracts** / MSS | **By design**: contract MSS compilation and storage untouched; not owned by sandbox. |
| Other portal tools (`operations`, `paypal_*`, etc.) | **Not row/resource editors** for anthology/sandbox in this audit scope; revisit if they gain datum writes. |

## What should become shared next (extraction targets)

1. **`build_tool_sandbox_runtime_deps_from_workspace(workspace, ...)`** — single factory used by `register_data_routes` and optionally AGRO if workspace is available on tool requests.
2. **Anthology promotion hook** — thin adapter from `workspace.update_anthology_profile` already inlined in `data_workspace.py`; could move to `_shared/portal/sandbox/promotion_hooks.py`.
3. **Flavor workspace**: shared helpers for “canonical rows payload” + config path resolution already live in data_engine; continue peeling duplicate branches only when low-risk.

## Tool session API (generic, not AGRO-only)

| Method | Path |
|--------|------|
| Open / create (optional `reopen` + `session_id`) | `POST /portal/api/data/sandbox/tool_session/open` |
| Get | `GET /portal/api/data/sandbox/tool_session/<session_id>` |
| Stage (`resources`, `anthology_rows` or alias `staged_rows`) | `POST .../stage` |
| Promote | `POST .../promote` |
| Refresh canonical anthology snapshot | `POST .../refresh` |
| Understanding + policy snapshot | `GET .../understanding` |
| Close | `DELETE .../close` |

## AGRO as first client

- **FND** `agro_erp` re-exports **TFF** implementation (`fnd/portal/tools/agro_erp/__init__.py`) — single codepath.
- AGRO uses **`get_tool_sandbox_session_manager(current_app)`** so sessions align with the data API registry when both are mounted on the same app.

## Hard constraints (unchanged)

- Contract authority and MSS contract compilation **remain outside** sandbox session.
- Data Tool / workbench **remains anthology-authoritative**.
- `ToolSandboxSession` is **staging only**; promotion uses `LocalResourceLifecycleService` + workspace hooks.
- `ambiguous` / `unknown` writable by default; **`invalid` blocks** promotion unless `rule_write_override` + reason where applicable.

## Remaining follow-up work

1. Migrate additional AGRO write surfaces (MVP product/invoice apply) through session + shared APIs where they touch sandbox resources.
2. Optional: real `ambiguous`-only payload test (no mock) alongside existing `evaluate_resource_payload_write` mock tests.
3. Thin FND/TFF `workspace.py` using shared session dep factory.
4. UI: surface session id + staged vs saved in AGRO ERP panels (minimal).
