# AGRO-ERP and Portal Data Foundation — Progress

This document tracks **current state, completed work, and next steps** for the AGRO-ERP tool and the shared data/contract foundation. It is updated as implementation advances.

---

## Current State (summary)

- **Runtime wiring**: AGRO-ERP is enabled in TFF `build.json`, mounted under `peripherals.tools`, and registered via `get_tool()`; it appears in the activity bar.
- **Existing AGRO-ERP code**: Handles property geometry only (config tokens, daemon resolution, coordinate decoding). No datum-identity layer or public resolver yet; taxonomy and product-type features were added on top of the current contract/MSS path.
- **Implemented (pre-tune)**:
  - Shared `inherited_taxonomy` service: loads taxonomy from contract MSS or local anthology via `load_inherited_taxonomy()`.
  - Tool data-spec schema and loader (`portal/tools/specs.py`), plus AGRO-ERP spec at `private/tools/agro_erp.spec.json` (inherited inputs, outputs, mediation).
  - AGRO-ERP model includes taxonomy context and product-type archetype; UI shows taxonomy tree and archetype table.
  - Product-type save endpoint `POST /portal/tools/agro_erp/product_types` writes to anthology via workspace and currently logs to **request_log** (to be moved to local audit log).
- **Not yet in place**: Datum identity module; contract compact-array as compiled snapshot; public contact-card resolver; contract update protocol; local audit log; request_log restricted to external use only.

---

## Completed (foundation and tuning)

- [x] **Intention document** ([AGRO_ERP_INTENTION.md](AGRO_ERP_INTENTION.md)): goals, design decisions, resolution order, contract modes, what not to freeze.
- [x] **Progress document** (this file): current state and next steps.
- [x] **Datum identity module** (`portals/_shared/portal/data_engine/datum_identity.py`): parse/normalize, compare for semantic equivalence, resolve to local row or contract entry, stable_datum_id, compile_compact_array_entries_keyed_by_path.
- [x] **Contract compact-array as compiled snapshot**: [CONTRACT_COMPACT_INDEX.md](CONTRACT_COMPACT_INDEX.md) documents index shape and entry keying by datum path.
- [x] **Public datum resolver** (`portals/_shared/portal/services/public_datum_resolver.py`): resolution order (local anthology → contract snapshot → public export); `resolve_datum_path`, `resolve_from_public_export`, `public_export_metadata_from_contact_card`.
- [x] **Contract update protocol**: [CONTRACT_UPDATE_PROTOCOL.md](CONTRACT_UPDATE_PROTOCOL.md) documents revisioned patch model and optional contract schema fields.
- [x] **Local audit log** (`portals/_shared/portal/services/local_audit_log.py`): `append_audit_event` to `private/audit/tool_actions.ndjson`; AGRO-ERP product_type save uses it instead of request_log.
- [x] **AGRO-ERP doc reframing**: [AGRO_ERP_TOOL.md](AGRO_ERP_TOOL.md) reframed as agricultural data workbench, capability buckets, local audit for tool CRUD.

---

## Next Steps (in preferred order)

1. **Datum identity module** (`portals/_shared/portal/data_engine/datum_identity.py`)
   - Parse/normalize refs; compare for semantic equivalence (canonical dot).
   - Resolve canonical datum path to local row, foreign/public source, or contract snapshot entry.
   - Generate stable identifier for a datum path independent of local iteration compaction.
   - Rule: datum path = semantic identity; layer/value_group/iteration = storage address.

2. **Contract compact-array as compiled snapshot**
   - Document schema for compiled datum index (revision, entries keyed by datum path).
   - Optionally add compiler that produces this index from current owner_mss + selected_refs.

3. **Public / contact-card datum resolver** (`portals/_shared/portal/services/public_datum_resolver.py`)
   - Read contact-card `accessible` / exported datum metadata.
   - Normalize exported refs; implement resolution order with public path before contract.
   - Expose stable public lookup; return source metadata without assuming a contract exists.

4. **Contract update protocol**
   - Document revisioned patch model and message shape.
   - Optional: add contract schema fields for relationship_mode, access_mode, sync_mode.

5. **Tool-spec**
   - Keep storage bindings loose (optional storage_anchors; no fixed layer/value_group in spec).
   - Add optional public_inputs / contract_inputs if needed for resolver integration.

6. **Local audit log**
   - New append-only surface for local tool/data-engine actions (e.g. `private/audit/tool_actions.ndjson` or under `daemon_state`).
   - Use for events such as `agro.product_type.created`; do **not** use request_log for local AGRO-ERP CRUD.

7. **AGRO-ERP doc reframing**
   - Update [AGRO_ERP_TOOL.md](AGRO_ERP_TOOL.md): purpose (agricultural data workbench), capability buckets, current vs planned capabilities; avoid locking full API contract.

8. **AGRO-ERP behavior**
   - Switch product_type save to use local audit log instead of request_log.
   - Optionally wire inherited taxonomy resolution through public resolver when available, then contract path.

---

## References

- [AGRO_ERP_INTENTION.md](AGRO_ERP_INTENTION.md) — goals and design decisions.
- [AGRO_ERP_TOOL.md](AGRO_ERP_TOOL.md) — tool purpose, routes, and capabilities (to be reframed).
- [MSS_COMPACT_ARRAY_SPEC.md](MSS_COMPACT_ARRAY_SPEC.md) — current MSS/contract compact-array behavior.
- [REQUEST_LOG_V1.md](REQUEST_LOG_V1.md) — request log envelope and usage (external only for TFF↔FND).
