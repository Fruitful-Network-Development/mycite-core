# Portal core consolidation — architecture memo

This document answers Phases 1–13 from the sandbox/tool consolidation request.  
**Policy:** `RulePolicy` v2 — `ambiguous` / `unknown` are writable; only `invalid` blocks by default (see `docs/datum_rule_policy_v2.md`).

---

## 1. Current-state audit (Phase 1)

### Already shared correctly

| Area | Location |
|------|-----------|
| Sandbox engine (stage/save/compile, SAMRAS, MSS) | `portals/_shared/portal/sandbox/engine.py` |
| **Tool sandbox session** (runtime staging + promote) | `portals/_shared/portal/sandbox/tool_sandbox_session.py` |
| **Session manager on Flask app** | `portals/_shared/portal/sandbox/session_registry.py` (`get_tool_sandbox_session_manager`) |
| Local resource lifecycle facade | `portals/_shared/portal/sandbox/local_resource_lifecycle.py` |
| Anthology canonical context | `portals/_shared/portal/data_engine/anthology_context.py` |
| Rule families + lenses + **RulePolicy v2** | `portals/_shared/portal/data_engine/rules/` |
| Write/probe evaluation | `rules/write_evaluation.py` |
| Data API surface (anthology, sandbox resources, rules, inherited) | `portals/_shared/portal/api/data_workspace.py` |
| Inherited subscription service | `portals/_shared/portal/data_engine/inherited_contract_resources.py` |
| External resolver / contract MSS (unchanged canonical) | `data_engine/external_resources/` |
| Shared Data Tool shell + `data_tool.js` (FND) | `runtime/flavors/fnd/portal/ui/...` |

### Still duplicated / parallel

| Area | Notes |
|------|--------|
| **FND vs TFF** | ~310 files under `runtime/flavors/`; `fnd` and `tff` each carry `app.py`, portal API shims, `workspace.py` (large). Goal: thin flavor wrappers only. |
| **Workspace implementation** | `flavors/*/data/engine/workspace.py` — twin copies; anthology authority and NIMM live here while rules/sandbox are shared — further extraction possible. |
| **AGRO flows** | Plot draft uses **`ToolSandboxSession`**; MVP/compile paths still partially direct — see `docs/portal_core_tool_sandbox_consolidation_audit.md`. |

### Still bypassing sandbox / shared engine

| Area | Notes |
|------|--------|
| **Anthology mutations** | Correctly go through flavor `workspace` + storage (authoritative); not sandbox — by design for Data Tool. |
| **Some tool flows** | Any route that writes rows without `understand_datums` / `evaluate_*` — audit per new tool. |
| **Legacy table/staging endpoints** | Marked deprecated in `data_workspace.py`; compatibility reads only. |

### Mess / size drivers

- Large per-flavor `workspace.py` + `app.py`.
- Config/progeny branches (`progeny_configs`, tenant/client JSON) spread across flavors.
- Multiple portal API entry modules per flavor duplicating registration glue.

---

## 2. Revised RulePolicy (Phase 2)

Implemented in code (`policy.py` v2 + `write_evaluation.py`). Summary table in `docs/datum_rule_policy_v2.md`.

---

## 3. Canonical sandbox **workspace** contract (Phase 3)

**Intent (freeze):**

1. **Open workspace** — tool/session id + data root; optional seed from anthology slice and/or resource ids.
2. **Load** — copy canonical rows into sandbox resource payload or staged JSON (existing `SandboxEngine` files under resources root).
3. **Edit** — same row grammar as anthology/resources; `understand_datums` + `RulePolicy` on staged payload.
4. **Validate** — `evaluate_resource_payload_write` / probe helpers; **block only on invalid** graph; ambiguous/unknown → warnings only.
5. **Compile / publish** — existing `LocalResourceLifecycleService` + `compile_*` / `publish` paths; anthology promotion remains **workspace** (`append_anthology_datum`, profile update) when promoting from tool via **`ToolSandboxSession.promote`** hooks + `POST /portal/api/data/sandbox/tool_session/.../promote`.

**Staging policy (freeze):** always compute understanding; surface status; invalid distinct; ambiguous/unknown allowed and labeled; canonical save respects invalid gate (+ override).

---

## 4. Canonical **tool / sandbox** contract (Phase 4)

Tools declare **intent**; engine owns semantics.

| Field | Meaning |
|-------|---------|
| `tool_id` | Stable id (e.g. `agro_erp`) |
| `required_resources` / `optional_resources` | `resource_id` + scope |
| `config_coordinate_paths` | Dotted paths read into `loaded_config_inputs` |
| `optional_sandbox_resource_id_paths` | Config paths → optional sandbox resource ids |
| `datum_families_touched` | e.g. `collection`, `field` — for UX only |
| `consumes_anthology_refs` | Datum ids or patterns tool reads |
| `publish_resource_kinds` | e.g. `mss_resource`, `samras`, future `msn_lookup_table` |
| `sandbox_layout` | Optional: which staged files / resource ids |

**Reference implementation (code):** `portals/_shared/portal/sandbox/workspace_contract.py` (TypedDicts).

---

## 5. Grammar unification plan (Phase 5)

| Mechanism | Status |
|-----------|--------|
| `DatumUnderstanding` | Shared |
| `RulePolicy` v2 | Shared |
| `evaluate_probe_write` / resource evaluate | Shared |
| Reference filter + inference | Shared API; UI: Data Tool uses table payload — extend all tool UIs to same fields |
| Lens | `resolve_lens_for_datum` + `rule_policy` |

**Gap:** dedicated “tool sandbox panel” UI — reuse Data Tool row components or shared partials.

---

## 6. Resource-type extensibility (Phase 6)

**Model:** “structural resource” = rows/state in `anthology_compatible_payload` or `canonical_state.compact_payload` + optional type-specific lens/compile (`SAMRAS` today).

**Next types** (e.g. MSN lookup table): register `resource_kind`, reuse `LocalResourceLifecycleService` + `understand_datums`; add **one** compile/publish adapter in `SandboxEngine`, not a new editor stack.

---

## 7. Reference inference (Phase 7)

- Continue improving `infer_reference_filter_rule_key` (parent + VG + magnitude).
- On failure: **warning + manual catalog** (existing `ref_entry_mode=manual` + ack); do not block writes.

---

## 8. Config / host / profile (Phase 8)

- Bias: single **active config** document shape; flavor injects theme + feature flags only.
- Reduce `if flavor ==` in `app.py` by moving registration into shared bootstrap with flavor plugin dict.

---

## 9. Runtime / flavor (Phase 9)

- Prefer **one** `portal.css` / shell template owner under `_shared/runtime` (ongoing dedupe).
- Flavor: `app.py` registers routes + sets `MYCITE_DATA_WORKSPACE` class path only.

---

## 10. Route / API ownership (Phase 10)

| Concern | Owner |
|---------|--------|
| Local resource lifecycle | `LocalResourceLifecycleService` |
| Inherited subscription | `InheritedSubscriptionService` |
| Sandbox file CRUD | `SandboxEngine` |
| Tool sandbox session | `ToolSandboxSession` / `ToolSandboxSessionManager` + `/portal/api/data/sandbox/tool_session/*` |
| Anthology writes | Flavor `workspace` (Data Tool authority) |
| Rule evaluation | `data_engine.rules` |

---

## 11. UI (Phase 11)

- Same status/badge/lens/ref behavior for anthology table — **done** in Data Tool for anthology.
- **Next:** resource editors and tool sandboxes consume identical API payloads (`datum_understanding`, `rule_policy_by_id`, `guidance_notes`).

---

## 12. Tests (Phase 12)

- `tests/test_datum_rule_families.py` — policy matrix, graph block semantics, routes (with Flask).
- `tests/test_tool_sandbox_session.py` — session open, stage, promote, policy gates; route tests via Flask app where registered.

---

## 13. Follow-up work

1. Extract shared `workspace.py` core from FND/TFF into `_shared` module.
2. ~~Implement `ToolSandboxSession` + generic tool session routes~~ — done (`tool_sandbox_session.py`, `/portal/api/data/sandbox/tool_session/*`).
3. ~~Migrate AGRO-ERP plot draft to sandbox session~~ — done; extend other AGRO write paths incrementally.
4. Session ownership freeze: `docs/tool_sandbox_session_ownership.md`.
4. Structural resource registry for new kinds (lookup table).
5. Further shell/CSS dedupe between flavors.
