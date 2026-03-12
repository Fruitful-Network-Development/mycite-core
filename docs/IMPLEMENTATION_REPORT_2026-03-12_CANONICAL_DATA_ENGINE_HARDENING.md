# Implementation Report — Canonical MyCite Data Engine Hardening (2026-03-12)

## A) Post-Implementation Audit Snapshot (A–J)

- A Canonical anthology model: Implemented for FND/TFF/MT runtime via shared normalization, deterministic ordering, shared compaction.
- B Mediation registry: Implemented as first-class typed registry (matcher/decode/encode/validate/render-hint).
- C AITAS model: Implemented with explicit phases and `spatial` + `spacial` compatibility.
- D NIMM alignment: Implemented for phase-aware transitions; pattern hooks activated.
- E Daemon layer: Implemented with explicit policy metadata and token-resolution route.
- F Progeny/member/alias model: Implemented baseline class metadata + runtime inheritance link pass; compatibility aliases retained.
- G Integration refs: Preserved existing FND integration endpoints; no external contract break.
- H Workbench graph model: Implemented focus/depth/context/layout controls and focus/investigation interaction binding.
- I Geographic/spatial base: Implemented shared geography model consumption on FND/TFF network pages.
- J Shell/UI relation: SYSTEM anthology workbench remains primary; UI consumes engine/API state.

## 1) File-by-File Change Summary

Shared engine/model:

- `portals/_shared/portal/data_engine/anthology_normalization.py`
  - Added canonical parse/sort/compaction helpers.
- `portals/_shared/portal/data_engine/__init__.py`
  - Exported shared normalization utilities.
- `portals/_shared/portal/mediation/registry.py`
  - Refactored to first-class mediation type specs + registry metadata + validation pipeline.
- `portals/_shared/portal/mediation/__init__.py`
  - Exported `resolve_entry` and `list_registry_entries`.
- `portals/_shared/portal/progeny_model/inheritance.py`
  - Fixed `alias_profile_overrides` merge semantics.
- `portals/_shared/portal/core_services/network_cards.py`
  - Switched to shared progeny canonicalization.
  - Added alias/progeny inheritance resolution and model metadata (`legal_entity_baseline_classes`, `inheritance_rules`).

Portal engine adapters:

- `portals/mycite-le_fnd/data/storage_json.py`
- `portals/mycite-le_tff/data/storage_json.py`
- `portals/mycite-ne_mt/data/storage_json.py`
  - Consume shared `datum_sort_key`.

- `portals/mycite-le_fnd/data/engine/workspace.py`
- `portals/mycite-le_tff/data/engine/workspace.py`
- `portals/mycite-ne_mt/data/engine/workspace.py`
  - Consume shared normalization/registry.
  - AITAS phase wiring.
  - Pattern hook activation.
  - Graph endpoint controls.
  - Daemon policy metadata + token resolver.

- `portals/mycite-le_fnd/data/engine/nimm/state.py`
- `portals/mycite-le_tff/data/engine/nimm/state.py`
- `portals/mycite-ne_mt/data/engine/nimm/state.py`
  - Canonical `spatial` + `spacial` compatibility and `aitas_phase`.

API routes:

- `portals/mycite-le_fnd/portal/api/data_workspace.py`
- `portals/mycite-le_tff/portal/api/data_workspace.py`
- `portals/mycite-ne_mt/portal/api/data_workspace.py`
  - Added graph query controls and `daemon/resolve_tokens` route.

Workbench UI:

- `portals/mycite-le_fnd/portal/ui/templates/tools/partials/data_tool_shell.html`
- `portals/mycite-le_tff/portal/ui/templates/tools/partials/data_tool_shell.html`
  - Graph controls (focus/depth/context/layout + zoom actions).

- `portals/mycite-le_fnd/portal/ui/static/tools/data_tool.js`
- `portals/mycite-le_tff/portal/ui/static/tools/data_tool.js`
  - Graph query wiring.
  - Click/dblclick focus+investigation flow.
  - Pan/zoom bindings + button handlers.
  - Focus/context visual state.

- `portals/mycite-le_fnd/portal/ui/static/portal.css`
- `portals/mycite-le_tff/portal/ui/static/portal.css`
  - Focus/context graph styles.

Network geography consumption:

- `portals/mycite-le_fnd/app.py`
- `portals/mycite-le_tff/app.py`
- `portals/mycite-le_fnd/portal/ui/templates/services/network.html`
- `portals/mycite-le_tff/portal/ui/templates/services/network.html`
  - Network page now consumes shared geography model output.

Tool integration:

- `portals/mycite-le_tff/portal/tools/agro_erp/__init__.py`
  - Daemon execution path now engine-backed when available.
  - Added `spatial` facet compatibility in daemon metadata.

Tests:

- `tests/test_anthology_normalization.py` (new)
- `tests/test_mediation_registry_contract.py` (new)
- `tests/test_workspace_aitas_daemon.py` (new)
- `tests/test_progeny_inheritance_runtime.py` (new)

Docs:

- `docs/CANONICAL_DATA_ENGINE.md` (new)
- `docs/DATA_TOOL.md` (updated)
- `docs/IMPLEMENTATION_REPORT_2026-03-12_CANONICAL_DATA_ENGINE_HARDENING.md` (new)

## 2) Data-Engine Summary

The workbench runtime is anthology-authoritative with shared deterministic normalization and engine-owned state transitions. Storage/workspace adapters now consume shared ordering/compaction utilities.

## 3) Mediation Registry Summary

Mediation types are first-class entries with explicit matcher/decode/encode/validation/render-hint contracts. Compatibility wrappers still route through the canonical typed registry.

## 4) Anthology-Normalization Summary

Ordering and compaction are now centralized. `compact_iterations` produces deterministic identifier remaps and sorted row payloads consumed by portal storage/workspace adapters.

## 5) AITAS State Summary

AITAS facets are explicit in engine state with phase transitions (`navigate`, `focus`, `investigate`, `mediate`). Canonical `spatial` is emitted while maintaining legacy `spacial` compatibility.

## 6) NIMM Engine Summary

`nav/inv/med/man` directives now drive phase/facet updates in engine state. Pattern recognizer hooks were moved from scaffold intent to active metadata + row annotation.

## 7) Daemon-Layer Summary

Daemon contracts now include policy metadata, action scope enforcement, default focus behavior, and output strategy. Token resolution route (`daemon/resolve_tokens`) provides constrained mediation-backed resolution.

## 8) Progeny/Member/Alias Model Summary

Runtime model now exposes baseline legal-entity classes and performs alias/progeny inheritance resolution via shared rule helper. Legacy type aliases (`tenant`, `board_member`) remain compatible.

## 9) Workbench Graph Summary

Graph endpoint supports `focus/depth/layout/context`. UI binds click to focus summary, double-click to investigation flow, and includes pan/zoom controls with focus-local rendering support.

## 10) Integration-Ref Summary

No public integration route break for existing FND integrations; runtime enhancements stay additive. AGRO ERP now prefers canonical engine-backed daemon resolution where available.

## 11) Geographic/Spatial Model Summary

Shared geography model decodes fixed-hex coordinate references and produces SVG/GeoJSON outputs consumed by network landing pages in FND and TFF.

## 12) Route/Page Summary

Stable routes remain intact (`/portal/api/data/state`, `/directive`, `/anthology/table`, `/anthology/graph`, `/daemon/*`). SYSTEM workbench remains the primary anthology interaction page.

## 13) Remaining TODOs (Real Repo Ambiguity)

- Non-target legacy portal paths still contain transitional code paths and should be retired in a dedicated cleanup pass.
- Time-series/SAMRAS endpoint families are still present for compatibility and should be explicitly gated/deprecated by policy decision.
- Further formalization of inheritance between progeny instance JSON and alias profile schemas can be expanded once canonical instance data is finalized.
- Additional end-to-end browser validation is required in runtime environments where JS bundling/runtime differs from unit-test environment.
