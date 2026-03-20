# Portal sandbox session — AGRO MVP + SAMRAS workspace pass

## Summary

This pass tightens **session-native** AGRO ERP behavior, adds **shared promotion hooks**
for profile/config writes, exposes a **generic SAMRAS workspace** HTTP surface, and
surfaces **staged vs saved** semantics in the AGRO UI.

## AGRO ERP (`agro_erp`)

- **Compile / adapt** for MVP resources is owned by
  `portals/_shared/portal/sandbox/agro_mvp_session.py` (`compile_agro_mvp_resource_context`).
- **Inherited preview** uses `preview_agro_mvp_inherited_field_with_msn` (shared module).
  When `field_ref_bindings` is empty but `field_usable_refs` is populated, bindings are
  synthesized via `build_field_ref_bindings` so selection stays aligned with adapter data.
- **Sessions**: `mvp/resource/select_or_load` attaches compile output to
  `ToolSandboxSession.ephemeral_tool_state["agro_mvp"]["compile"]` and returns
  `sandbox_session_id` + `session` snapshot.
- **Preview** stages `WritePreviewResult` dicts on the session via
  `stage_tool_config_write` (`inherited_product_profile_ref` / `inherited_supply_log_ref`).
- **Apply** promotes through `ToolSandboxSession.promote` using
  `build_tool_sandbox_promotion_hooks` (`promotion_hooks.py`), not a direct
  `apply_write_preview` call in the route.
- **Explicit promote**: `POST /portal/tools/agro_erp/mvp/session/promote`.

## Shared core

- `ToolSandboxSession` now tracks:
  - `ephemeral_tool_state` (tool-owned snapshots; not persisted by promote),
  - `staged_tool_config_writes` + `promotion_targets["tool_config_writes"]`.
- `ToolSandboxPromotionHooks.apply_tool_config_write` applies staged profile previews.
- `write_preview_result_from_dict` rehydrates previews in
  `portals/_shared/portal/data_engine/write_pipeline.py`.
- `build_tool_sandbox_promotion_hooks` centralizes anthology + config promotion for
  `register_data_routes` and tools.

## SAMRAS workspace (generic)

- `build_samras_workspace_view_model` in `txa_sandbox_workspace.py` aliases the TXA table
  helpers with schema `mycite.portal.sandbox.samras_workspace.view_model.v1` and
  `workspace_family: samras_title_tree`.
- `GET /portal/api/data/sandbox/samras_workspace?resource_id=&selected_address=&sandbox_session_id=`
  returns `{ ok, view_model }`, optionally overlaying `working_resources[resource_id]` from
  the tool session.

## Tests

- `tests/test_agro_erp_tool_flow.py` seeds an on-disk `mycite-config-<msn>.json` so
  `_save_active_config_for_write` can resolve a path (matches production resolver rules).
- `tests/test_tool_sandbox_session.py` covers staged config promotion and the SAMRAS route.

## Follow-ups

- TFF/FND `data/engine/workspace.py` remain byte-level duplicates; extract only after a
  mechanical diff gate.
- Deeper TXA “reverse mutation” remains explicitly **staged/honest** where the repo is
  not ready to canonicalize.
