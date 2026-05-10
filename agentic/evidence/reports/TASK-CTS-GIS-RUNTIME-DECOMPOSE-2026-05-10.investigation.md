# Investigation Report: CTS-GIS Runtime Decomposition

**Task:** TASK-CTS-GIS-RUNTIME-DECOMPOSE-2026-05-10  
**Date:** 2026-05-10  
**Status:** Complete — ready to plan

---

## Current State

`MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py` — 4,578 lines,
98 functions, 5 distinct functional domains with no internal separation.

Three functions account for 1,228 lines (27% of the file):
- `build_portal_cts_gis_surface_bundle` — 515 LOC
- `_build_cts_gis_structured_interface_body` — 412 LOC
- `_apply_cts_gis_action` — 401 LOC

---

## Proposed Layout

```
instances/_shared/runtime/
├── portal_cts_gis_runtime.py     ← thin re-exporter (~20 LOC)
└── _cts_gis/
    ├── __init__.py
    ├── _utils.py                 (~280 LOC) primitive helpers, no internal deps
    ├── _tool_state.py            (~340 LOC) state normalize/merge/resolve
    ├── _navigation.py            (~500 LOC) SAMRAS decode, dropdown builders
    ├── _service.py               (~400 LOC) datum store, live read, evidence
    ├── _directive.py             (~440 LOC) control panel assembly
    ├── _interface.py             (~750 LOC) interface body, projections, staging
    ├── _action.py                (~500 LOC) action dispatch and handlers
    └── _bundle.py                (~100 LOC) public entry points
```

---

## Import Graph (acyclic DAG)

```
_bundle.py → _interface.py, _action.py, _directive.py, _navigation.py,
             _service.py, _tool_state.py, _utils.py
_interface.py → _navigation.py, _service.py, _tool_state.py, _utils.py
_action.py    → _service.py, _tool_state.py, _utils.py
_directive.py → _navigation.py, _tool_state.py, _utils.py
_navigation.py → _tool_state.py, _utils.py
_service.py   → _utils.py
_tool_state.py → _utils.py
_utils.py     → (external only)
```

No cycles. All imports flow toward `_utils.py`.

---

## Function Inventory (by proposed module)

### `_utils.py` — 25 functions
Helpers with no internal dependencies: `_as_text` wrappers, `LegacyMapsAliasUnsupportedError`,
`_path_or_none`, `_safe_json_object`, `_dedupe_warnings`, workbench document
helpers, legacy alias checks, geometry utilities, `_split_row_source`, `_row_data_tokens`.

Owns the two module-level mutable caches:
- `_DATUM_STORE_BY_DATA_DIR`
- `_DATUM_STORE_BY_AUTHORITY_DB`

### `_tool_state.py` — 8 functions
`_normalize_tool_state`, `_merge_tool_state`, `_tool_state_clone`,
`_request_tool_state_overrides`, `_resolved_tool_state`,
`_strict_projection_context_differs`, `_apply_selected_node_state`,
`_clear_selection_state`, `_canonical_staged_selection_state`,
`_tool_state_for_navigation`, `_staged_insert_state`.

### `_navigation.py` — 18 functions
`_build_directory_dropdown_navigation` (322 LOC — kept whole),
`_navigation_canvas_from_compiled_artifact` (125 LOC — kept whole),
node utilities, SAMRAS decode, shell request builders.

### `_service.py` — 13 functions
Datum store getters, path resolution, `_read_live_service_surface`,
`_build_source_evidence`, `_datum_summary`, `_cts_gis_contract_state`.

### `_directive.py` — 6 functions
`_build_cts_gis_directive_panel` (270 LOC), `_build_cts_gis_context_controls`
(104 LOC), panel component helpers, `_cts_gis_control_panel_file_entries`.

### `_interface.py` — 15 functions
`_build_cts_gis_structured_interface_body` (412 LOC — kept whole),
`_service_surface_from_compiled_artifact`, `_navigation_canvas_from_compiled_artifact`,
projections, staging widgets, data browsers, public data filters.

### `_action.py` — 10 functions
`_apply_cts_gis_action` (401 LOC — kept whole), `_compile_staged_nimm_envelope`,
`_cts_gis_action_result`, audit helpers, action builders, `_normalize_action_request`.

### `_bundle.py` — 3 functions
`build_portal_cts_gis_surface_bundle` (515 LOC — kept whole),
`run_portal_cts_gis`, `run_portal_cts_gis_action`.

---

## Tightly Coupled Functions (not split)

Four large functions are tightly coupled to their local state and cannot be
decomposed without passing 20+ arguments. They are assigned to their module but
kept as single functions:

- `build_portal_cts_gis_surface_bundle` (515 LOC) → `_bundle.py`
- `_build_cts_gis_structured_interface_body` (412 LOC) → `_interface.py`
- `_apply_cts_gis_action` (401 LOC) → `_action.py`
- `_build_directory_dropdown_navigation` (322 LOC) → `_navigation.py`

---

## Architecture Boundary Test Risk: None

`test_portal_one_shell_boundaries.py` checks:
- File `portal_cts_gis_runtime.py` exists — satisfied (re-exporter kept)
- `run_portal_shell_entry` called — in `run_portal_cts_gis()` re-exported to main module
- Specific symbols (`cts_gis_interface_panel_render_key`, `precinct_district_overlay_enabled`) — live in `_interface.py`, still visible via re-exporter

No architecture test changes required.

---

## Migration Sequence (10 phases, one step at a time)

Each phase creates one sub-module, moves functions from the monolith, runs
tests. Tests must pass before the next phase begins.

| Phase | Action | Risk |
|---|---|---|
| 1 | Create `_cts_gis/` directory + empty `__init__.py` | None |
| 2 | Extract `_utils.py` (25 helpers, no internal deps) | Low |
| 3 | Extract `_tool_state.py` (depends only on `_utils`) | Low |
| 4 | Extract `_service.py` (datum store, evidence, live read) | Low |
| 5 | Extract `_navigation.py` (SAMRAS decode, dropdown, shell requests) | Medium |
| 6 | Extract `_directive.py` (control panel assembly) | Medium |
| 7 | Extract `_interface.py` (interface body, projections, artifacts) | Medium |
| 8 | Extract `_action.py` (action dispatch) | Medium |
| 9 | Extract `_bundle.py` (public entry points) | Low |
| 10 | Convert `portal_cts_gis_runtime.py` to thin re-exporter | Low |

After Phase 10, `portal_cts_gis_runtime.py` becomes:
```python
from ._cts_gis._bundle import (
    build_portal_cts_gis_surface_bundle,
    run_portal_cts_gis,
    run_portal_cts_gis_action,
)
__all__ = [...]  # unchanged
```

---

## Test Coverage Note

`test_portal_cts_gis_runtime.py` imports `_normalize_request` and
`run_portal_cts_gis` directly from `portal_cts_gis_runtime`. Both must remain
in `__all__` and be re-exported from the main module. `_normalize_request` lives
in `_service.py`; it must be included in the thin re-exporter's imports.
