# Shell region kinds (V2 admin portal)

This document is the **canonical wire contract** for `shell_composition.regions` in the V2 admin portal shell, derived from the current Python runtime and `v2_portal_shell.js`. It is not a UX specification.

## Authority

Precedence and invariants are grounded in:

- [structural_invariants.md](../ontology/structural_invariants.md) — navigation purity; tools attach through shell-defined surfaces; browser JS is not alternate shell truth.
- [v2-authority_stack.md](../plans/v2-authority_stack.md) — documentation precedence.
- [interface_surfaces.md](../ontology/interface_surfaces.md) — shell vs tool surface rules.

Implementation sources of truth (enumerations and field shapes):

- `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py` — schemas, `build_shell_composition_payload`, `shell_composition_mode_for_surface`, `foreground_region_for_surface`, `inspector_collapsed_for_surface`, `build_portal_activity_dispatch_bodies`.
- `MyCiteV2/instances/_shared/runtime/admin_runtime.py` — `run_admin_shell_entry`, `_build_regions_and_surface`, region builders, `_apply_shell_chrome_to_composition`.
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js` — `applyChrome`, `renderActivityItems`, `renderControlPanel`, `renderWorkbench`, `renderInspector`.

## Shell composition contract vs presentation

| Layer | Responsibility |
|--------|----------------|
| **Shell composition contract** | Serializable JSON under `shell_composition` in the runtime envelope: `schema`, `composition_mode`, service/surface identifiers, collapse flags, `foreground_shell_region`, `regions.*`, and server-issued `shell_request` bodies in activity/control entries. Produced by `build_shell_composition_payload` and `run_admin_shell_entry` (including chrome overlays). |
| **Presentation behavior** | DOM/CSS, string truncation, `aria-*`, layout attributes on `.ide-shell`, inspector panel classes, table markup, and form wiring in JS. The client must not invent navigation POST bodies or alternate composition; it only renders what the runtime issued and dispatches using provided `shell_request` objects. |

Optional request hints (`AdminShellRequest.shell_chrome`) are merged into composition by the runtime (`requested_shell_chrome` echo and collapse overrides); they are **not** a second shell model (see `AdminShellChrome` in `admin_shell.py`).

## Top-level `shell_composition` fields

Emitted by `build_shell_composition_payload` in `admin_shell.py`, then updated in `run_admin_shell_entry` (`admin_runtime.py`: `page_title` / `page_subtitle` assignment) and optionally mutated by `_apply_shell_chrome_to_composition`.

| Field | Required | Meaning |
|-------|----------|---------|
| `schema` | yes | Always `mycite.v2.admin.shell.composition.v1` (`ADMIN_SHELL_COMPOSITION_SCHEMA`). |
| `composition_mode` | yes | `"tool"` or `"system"` from `shell_composition_mode_for_surface(active_surface_id)` (tool for AWS read-only, narrow-write, **AWS-CSM onboarding** (Band 4), **internal AWS-CSM sandbox**, and **Maps read-only** slice IDs; otherwise system). |
| `active_service` | yes | `"aws"`, `"maps"`, `"datum"`, `"registry"`, or `"system"` from `map_surface_to_active_service`. |
| `active_surface_id` | yes | Resolved active surface slice id (text). |
| `active_tool_slice_id` | conditional | Non-null only when `composition_mode == "tool"`; equals the active tool slice id for the current AWS or Maps tool surface. |
| `foreground_shell_region` | yes | `"interface-panel"` in tool mode; `"center-workbench"` in system mode, unless chrome forces otherwise (see below). |
| `control_panel_collapsed` | yes | Boolean; parameter to `build_shell_composition_payload`, may be overridden by chrome. |
| `inspector_collapsed` | yes | From `inspector_collapsed_for_surface` (true when not in tool mode), overridable by chrome. |
| `portal_tenant_id` | yes | Tenant id string for labeling and datum reads. |
| `page_title` | yes | Set by runtime (defaults to `"MyCite"` in builder). |
| `page_subtitle` | yes | Set by runtime after region build. |
| `regions` | yes | Object with keys `activity_bar`, `control_panel`, `workbench`, `inspector`. |
| `requested_shell_chrome` | optional | Present when the incoming request included non-empty `shell_chrome` (echo of client hints). |

### `composition_mode` and `foreground_shell_region`

- **Default mapping** (`admin_shell.py`): tool mode → `foreground_shell_region: "interface-panel"`; system mode → `"center-workbench"`.
- **Inspector chrome override** (`admin_runtime.py` `_apply_shell_chrome_to_composition`): if `composition_mode == "tool"` and the request sets `shell_chrome.inspector_collapsed` true, the runtime sets `foreground_shell_region` to `"center-workbench"` and may replace the workbench payload with `kind: "tool_collapsed_inspector"` so the center column carries the dismissal message.

### `inspector_collapsed` semantics

- Base value: `inspector_collapsed_for_surface` is true when **not** in tool mode (inspector collapsed in system layout), false in tool mode (inspector is the primary surface).
- Client (`applyChrome`): toggles `#portalInspector` collapsed class, `aria-hidden`, and `data-primary-surface` / `data-surface-layout` from `composition_mode`.

---

## Region: `activity_bar`

**Producer:** `build_shell_composition_payload` merges `regions.activity_bar`; items from `_activity_items` in `admin_runtime.py`.

**Schema:** `mycite.v2.admin.shell.region.activity_bar.v1` (`ADMIN_SHELL_REGION_ACTIVITY_BAR_SCHEMA`).

| Field | Required | Notes |
|-------|----------|--------|
| `schema` | yes | Activity bar region schema constant. |
| `dispatch` | yes | Literal `"post_admin_shell"` (dispatch channel name). |
| `items` | yes | Array of activity entries (may be empty if catalog filters remove all). |

### Activity item shape (each element of `items`)

| Field | Required | Notes |
|-------|----------|--------|
| `slice_id` | yes | Target slice id. |
| `label` | yes | Display label. |
| `active` | yes | Boolean: matches `nav_active_slice_id`. |
| `shell_request` | yes | Full `AdminShellRequest` body for POST (from `build_portal_activity_dispatch_bodies`). |
| `entrypoint_id` | optional | Present on tool registry entries from catalog. |
| `read_write_posture` | optional | Present on tool entries (`read-only` or `write`). |

**Client branch:** `renderActivityItems` in `v2_portal_shell.js` — builds links; dispatches `loadShell(item.shell_request)` on click.

There is no per-item `kind` discriminant; routing is entirely by the embedded `shell_request`.

---

## Region: `control_panel`

**Producer:** `_control_panel_region` in `admin_runtime.py`.

**Schema:** `mycite.v2.admin.shell.region.control_panel.v1`.

| Field | Required | Notes |
|-------|----------|--------|
| `schema` | yes | Control panel region schema. |
| `sections` | yes | Array of sections. |

### Section object

| Field | Required | Notes |
|-------|----------|--------|
| `title` | yes | Section heading (e.g. `"Admin surfaces"`, `"Shell-registered tools"`, `"Datum"`). |
| `entries` | yes | Array of entry objects. |

### Entry object

| Field | Required | Notes |
|-------|----------|--------|
| `label` | yes | Link label. |
| `meta` | optional | Secondary text (slice id or entrypoint id). |
| `active` | yes | Boolean. |
| `shell_request` | optional | Omitted when missing from dispatch bodies; gated tools may still appear with `gated: true`. |
| `gated` | optional | When true, client marks link disabled (`aria-disabled`). |

**Client branch:** `renderControlPanel` — iterates `sections` / `entries`; uses `shell_request` when present.

---

## Region: `workbench` — kinds

Workbench payloads use `schema: mycite.v2.admin.shell.region.workbench.v1` (`ADMIN_SHELL_REGION_WORKBENCH_SCHEMA`) and a **`kind`** string. The table lists kinds **emitted today** by `run_admin_shell_entry` → `_build_regions_and_surface` and chrome overlay (not hypothetical kinds).

| `kind` | Required fields (contract) | Optional / common | Runtime emitter(s) | Client branch (`renderWorkbench`) |
|--------|-----------------------------|-------------------|---------------------|-----------------------------------|
| `error` | `schema`, `kind`, `title`, `visible`, `message` | `subtitle` | `_workbench_error`; selection-blocked paths | `kind === "error"` — card + message |
| `home_summary` | `schema`, `kind`, `title`, `visible`, `blocks` | `subtitle` | `_workbench_home` | Parses `blocks` as label/value cards (`b.label`, `b.value`). Nested block `kind` (e.g. `"metric"`) is informational for authors; JS does not switch on it. |
| `tool_registry` | `schema`, `kind`, `title`, `visible`, `tool_rows` | `subtitle`, `banner` (`code`, `message`) | `_workbench_registry`; blocked registry path with `banner` | Table from `tool_rows`; optional banner |
| `datum_workbench` | `schema`, `kind`, `title`, `visible`, `summary`, `warnings`, `documents`, `rows_preview` | `subtitle` | `_workbench_datum` | Summary cards, authoritative document catalog, selected-document diagnostics, preview table columns `datum_address`, `recognized_family`, `diagnostic_states`, `primary_value_token`, and compact reference bindings |
| `tool_placeholder` | `schema`, `kind`, `title`, `visible` (`false` for AWS primary inspector layout), `subtitle` | — | AWS read-only, narrow-write, **AWS-CSM onboarding**, and **AWS-CSM sandbox** success paths | Treated like hidden body: `visible === false` shows empty/workbench-hidden copy; subtitle as message |
| `maps_workbench` | `schema`, `kind`, `title`, `visible`, `document_catalog`, `selected_document`, `selected_row`, `map_projection`, `rows`, `diagnostic_summary`, `lens_state`, `request_contract` | `subtitle`, `warnings` | `build_admin_maps_workbench` in `admin_maps_runtime.py`; `run_admin_shell_entry` maps branch | Geographic pane + document chooser + rows/feature cross-selection |
| `tool_collapsed_inspector` | `schema`, `kind`, `title`, `subtitle`, `visible` (`true`) | — | `_apply_shell_chrome_to_composition` only | Dedicated branch — dismissal card |

### Workbench presentation note

If `visible === false` or `kind === "hidden"` (not emitted by current Python paths), `renderWorkbench` shows a generic “Workbench hidden…” message. `tool_placeholder` relies on `visible: false` with `kind: "tool_placeholder"`.

---

## Region: `inspector` — kinds

Inspector payloads use `schema: mycite.v2.admin.shell.region.inspector.v1` (`ADMIN_SHELL_REGION_INSPECTOR_SCHEMA`) and a **`kind`** string.

| `kind` | Required fields (contract) | Optional | Runtime emitter(s) | Client branch (`renderInspector`) |
|--------|---------------------------|----------|---------------------|-------------------------------------|
| `empty` | `schema`, `kind`, `title` | `body_text` | `_inspector_empty` (default overview / registry / datum / errors) | Empty-state paragraph |
| `datum_summary` | `schema`, `kind`, `title`, `selected_document`, `readiness_status`, `source_files`, `warnings` | — | `_inspector_datum` | Definition list for the selected authoritative datum document plus diagnostic totals / warnings |
| `aws_read_only_surface` | `schema`, `kind`, `title`, `tenant_scope_id`, `mailbox_readiness`, `smtp_state`, `gmail_state`, `verified_evidence_state`, `selected_verified_sender`, `allowed_send_domains`, `write_capability`, `profile_summary` | `compatibility_warnings`, `inbound_capture`, `dispatch_health` | `_inspector_aws_read_only_surface` | Definition list + optional compatibility list |
| `aws_tool_error` | `schema`, `kind`, `title`, `error_code`, `error_message`, `warnings` | — | `_inspector_aws_tool_error` | Error card + warnings list |
| `narrow_write_form` | `schema`, `kind`, `title`, `read_only_context`, `submit_contract` | — | `_inspector_narrow_write_form` | Form + POST to `submit_contract.route` with schema and fixed fields |
| `csm_onboarding_form` | `schema`, `kind`, `title`, `read_only_context`, `submit_contract`, `onboarding_action_options` | — | `_inspector_csm_onboarding_form` | Select + `profile_id` + POST to `/portal/api/v2/admin/aws/csm-onboarding` using server-issued schema and fixed `tenant_scope` / `focus_subject` |
| `maps_summary` | `schema`, `kind`, `title`, `selected_document`, `selected_feature`, `selected_row`, `map_projection`, `diagnostic_summary`, `lens_state` | `warnings` | `build_admin_maps_inspector` in `admin_maps_runtime.py` | Selected document / feature / row summary for the maps slice |

### `json_document` inspector kind

- **Client:** `renderInspector` includes a branch for `kind === "json_document"` (`title`, `document`).
- **Runtime:** `_inspector_json` exists in `admin_runtime.py` but **no call path** in `run_admin_shell_entry` attaches it today. Treat as **reserved wire shape** for future emitters, not part of the live enumeration for verifier pass/fail against “currently emitted” kinds unless code starts calling `_inspector_json`.

---

## Extension notes (tools / surfaces)

- New **tool surfaces** should register slice ids in `admin_shell.py` (`build_admin_tool_registry_entries`, `shell_composition_mode_for_surface`, `map_surface_to_active_service` as needed), add dispatch bodies in `build_portal_activity_dispatch_bodies`, implement `_build_regions_and_surface` branches, and add any new **workbench/inspector kinds** with matching `renderWorkbench` / `renderInspector` branches.
- Do not add client-side-only `kind` values without a runtime emitter; the verifier should treat that as a contract violation.

---

## Related contracts

- [README.md](README.md) — contracts index and import terminology.
