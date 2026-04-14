# Shell region kinds (V2 admin portal)

This document is the **canonical wire contract** for `shell_composition.regions`
in the V2 admin portal shell, derived from the current Python runtime and the
ordered portal shell scripts loaded by `portal.html`. It is not a UX
specification.

## Authority

Precedence and invariants are grounded in:

- [structural_invariants.md](../ontology/structural_invariants.md) — navigation purity; tools attach through shell-defined surfaces; browser JS is not alternate shell truth.
- [v2-authority_stack.md](../plans/v2-authority_stack.md) — documentation precedence.
- [interface_surfaces.md](../ontology/interface_surfaces.md) — shell vs tool surface rules.

Implementation sources of truth (enumerations and field shapes):

- `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py` — schemas, `build_shell_composition_payload`, `shell_composition_mode_for_surface`, `foreground_region_for_surface`, `inspector_collapsed_for_surface`, `build_portal_activity_dispatch_bodies`.
- `MyCiteV2/instances/_shared/runtime/admin_runtime.py` — `run_admin_shell_entry`, `_build_regions_and_surface`, region builders, `_apply_shell_chrome_to_composition`.
- `MyCiteV2/instances/_shared/portal_host/templates/portal.html` — ordered
  shell script loading and `body[data-shell-boot-state]`.
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_core.js` —
  bootstrap, POST dispatch, envelope validation, chrome application, and boot
  state transitions.
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js`
  — tool-specific workbench renderers keyed by runtime `kind`.
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js`
  — tool-specific inspector renderers keyed by runtime `kind`.
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_watchdog.js`
  — visible fatal-state fallback when the shell bundle is missing or hydration
  stalls.

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
| `composition_mode` | yes | `"tool"` or `"system"` from `shell_composition_mode_for_surface(active_surface_id)`. This is now a semantic hint only; it no longer swaps the shell into a tool-only layout. |
| `active_service` | yes | `"system"`, `"network"`, or `"utilities"` from `map_surface_to_active_service`. This is now a root-service identifier, not a per-tool family label. |
| `active_surface_id` | yes | Resolved active surface slice id (text). |
| `active_tool_slice_id` | conditional | Non-null only when `composition_mode == "tool"`; equals the active tool slice id for the current AWS or CTS-GIS tool surface. |
| `foreground_shell_region` | yes | `"center-workbench"` or `"interface-panel"`. Mediation-first tools such as CTS-GIS may issue `"interface-panel"` as the foreground shell region. |
| `control_panel_collapsed` | yes | Boolean; parameter to `build_shell_composition_payload`, may be overridden by chrome. |
| `inspector_collapsed` | yes | Base shell state is collapsed by default; client chrome may explicitly open it. |
| `portal_tenant_id` | yes | Tenant id string for labeling and datum reads. |
| `page_title` | yes | Set by runtime (defaults to `"MyCite"` in builder). |
| `page_subtitle` | yes | Set by runtime after region build. |
| `regions` | yes | Object with keys `activity_bar`, `control_panel`, `workbench`, `inspector`. |
| `requested_shell_chrome` | optional | Present when the incoming request included non-empty `shell_chrome` (echo of client hints). |

### `composition_mode` and `foreground_shell_region`

- `composition_mode` remains in the wire contract so tool-aware renderers can
  branch when needed.
- The shell still owns foreground posture; the browser does not infer it.
- `foreground_shell_region` may be `interface-panel` for a mediation-first tool
  while the workbench remains mounted as secondary context.

### `inspector_collapsed` semantics

- Base value: root and workbench-primary surfaces remain collapsed by default.
- Interface-panel-primary tools default to `inspector_collapsed = false`.
- When a mediation-first tool is explicitly collapsed through `shell_chrome`,
  the runtime may swap the workbench to `kind: tool_collapsed_inspector` with a
  reopen action instead of silently reverting tool posture in the browser.

### DOM boot-state contract

- `body[data-shell-boot-state]` is runtime-visible hydration state:
  `template`, `bundle_loaded`, `shell_posting`, `hydrated`, or `fatal`.
- The browser may only advance this state through shell execution or the
  watchdog fatal fallback; it must not invent alternate shell legality.

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
| `label` | yes | Human-readable label; this is now also visibly rendered in the principal activity bar. |
| `aria_label` | yes | Accessibility label for the icon button. |
| `icon_id` | yes | Shell-owned icon identifier. |
| `nav_kind` | yes | `root_logo`, `root_service`, or `tool`. |
| `active` | yes | Boolean: matches `nav_active_slice_id`. |
| `shell_request` | yes | Full `AdminShellRequest` body for POST (from `build_portal_activity_dispatch_bodies`). |
| `href` | optional | Canonical deep-link path for the root or tool. |
| `entrypoint_id` | optional | Present on tool registry entries from catalog. |
| `read_write_posture` | optional | Present on tool entries (`read-only` or `write`). |
| `tool_kind` | optional | Present on tool entries only; root services are not tools. |
| `surface_posture` | optional | Present on tool entries only; currently `workbench_primary` or `interface_panel_primary`. |

**Client branch:** `renderActivityItems` in `v2_portal_shell.js` — builds compact icon + visible-label links; dispatches `loadShell(item.shell_request)` on click.

The runtime now emits the fixed root-shell order before visible tools:

1. root logo to `System`
2. `Network`
3. `System`
4. `Utilities`
5. visible tools in registry order

Canonical page routes aligned to this shell contract are:

- `/portal/system`
- `/portal/network`
- `/portal/utilities`
- `/portal/utilities/<tool_slug>`

Compatibility aliases remain:

- `/portal/system/<tool_slug>`
- `/portal/system/tools`

---

## Region: `control_panel`

**Producer:** `_control_panel_region` in `admin_runtime.py`.

**Schema:** `mycite.v2.admin.shell.region.control_panel.v1`.

| Field | Required | Notes |
|-------|----------|--------|
| `schema` | yes | Control panel region schema. |
| `kind` | yes | Page-specific control-panel kind such as `system_control_panel`, `network_control_panel`, `utilities_control_panel`, or `aws_csm_control_panel`. |
| `title` | optional | Region-local title. |
| `tabs` | optional | Root-tab navigation entries for root pages. |
| `sections` | yes | Array of sections. |

### Section object

| Field | Required | Notes |
|-------|----------|--------|
| `title` | yes | Section heading. |
| `entries` | yes | Array of entry objects. |

### Entry object

| Field | Required | Notes |
|-------|----------|--------|
| `label` | yes | Link label. |
| `meta` | optional | Secondary text (slice id or entrypoint id). |
| `active` | yes | Boolean. |
| `shell_request` | optional | Omitted when missing from dispatch bodies. |
| `href` | optional | Canonical deep-link path when present. |
| `gated` | optional | When true, client marks link disabled (`aria-disabled`). |

**Client branch:** `renderControlPanel` — switches on `kind`, renders page-specific module headers and root tabs, then iterates `sections` / `entries`; uses `shell_request` when present.

---

## Region: `workbench` — kinds

Workbench payloads use `schema: mycite.v2.admin.shell.region.workbench.v1` (`ADMIN_SHELL_REGION_WORKBENCH_SCHEMA`) and a **`kind`** string. The table lists kinds **emitted today** by `run_admin_shell_entry` → `_build_regions_and_surface` and chrome overlay (not hypothetical kinds).

| `kind` | Required fields (contract) | Optional / common | Runtime emitter(s) | Client branch (`renderWorkbench`) |
|--------|-----------------------------|-------------------|---------------------|-----------------------------------|
| `error` | `schema`, `kind`, `title`, `visible`, `message` | `subtitle` | `_workbench_error`; selection-blocked paths | `kind === "error"` — card + message |
| `tool_collapsed_inspector` | `schema`, `kind`, `title`, `visible`, `message`, `action_label`, `action_shell_chrome` | `subtitle` | `apply_surface_posture_to_composition` when an interface-panel-primary tool is explicitly collapsed | Shell-issued fallback card that reopens the interface panel |
| `system_root` | `schema`, `kind`, `title`, `visible`, `root_tab`, `root_tabs`, `blocks` | `subtitle`, `notes`, `sources_summary`, `sandbox_summary` | `_workbench_home` | System root workbench with root tabs (`home`, `sources`, `sandbox`), status cards, and datum-facing document summaries |
| `utilities_root` | `schema`, `kind`, `title`, `visible`, `root_tab`, `root_tabs`, `tool_rows` | `subtitle`, `banner`, `config_sections`, `vault_summary` | `_workbench_registry`; blocked registry path with `banner` | Utilities launcher/config/vault root; tool rows include shell-owned launch requests |
| `network_root` | `schema`, `kind`, `title`, `visible`, `root_tab`, `root_tabs`, `blocks`, `tab_panels` | `subtitle`, `notes` | `_workbench_network` | Contract-first hosted/network root with tabbed read-only entity summaries |
| `datum_workbench` | `schema`, `kind`, `title`, `visible`, `summary`, `warnings`, `documents`, `rows_preview` | `subtitle` | `_workbench_datum` | Summary cards, authoritative document catalog, selected-document diagnostics, preview table columns `datum_address`, `recognized_family`, `diagnostic_states`, `primary_value_token`, and compact reference bindings |
| `aws_csm_family_workbench` | `schema`, `kind`, `title`, `visible`, `family_health`, `domain_states` | `subtitle`, `selected_domain_state`, `selected_author`, `subsurface_navigation`, `gated_subsurfaces` | `_workbench_aws_csm_family` | Main AWS-CSM family landing in the workbench; interface panel remains secondary |
| `aws_csm_subsurface_workbench` | `schema`, `kind`, `title`, `visible`, `mode`, `help_text`, `profile_summary` | `subtitle`, `selected_verified_sender`, `mailbox_readiness`, `compatibility_warnings`, `submit_route` | `_workbench_aws_subsurface` | AWS subordinate slice context in the workbench, with the interface panel opened only when the operator chooses to |
| `cts_gis_workbench` | `schema`, `kind`, `title`, `visible`, `request_contract` | `subtitle`, `warnings`, `diagnostic_summary`, `mediation_state`, `lens_state`, `selected_document_id`, `selected_row_address`, `selected_feature_id`, `render_from_surface_payload` | `build_admin_cts_gis_workbench` in `admin_cts_gis_runtime.py`; `run_admin_shell_entry` CTS-GIS branch | Evidence-oriented CTS-GIS workbench with document switching, diagnostic summaries, projected-feature tables, selected-row evidence, and collapsible raw underlay driven from the canonical `surface_payload`; this surface stays mounted as secondary context even when the interface panel is foreground-primary |

### Workbench presentation note

If `visible === false` or `kind === "hidden"` (not emitted by current Python paths), `renderWorkbench` shows a generic “Workbench hidden…” message.

---

## Region: `inspector` — kinds

Inspector payloads use `schema: mycite.v2.admin.shell.region.inspector.v1` (`ADMIN_SHELL_REGION_INSPECTOR_SCHEMA`) and a **`kind`** string.

The inspector region may also carry presentation hints issued by the runtime:

- `primary_surface: bool`
- `layout_mode: sidebar | dominant`

| `kind` | Required fields (contract) | Optional | Runtime emitter(s) | Client branch (`renderInspector`) |
|--------|---------------------------|----------|---------------------|-------------------------------------|
| `empty` | `schema`, `kind`, `title` | `body_text` | `_inspector_empty` (default overview / registry / datum / errors) | Empty-state paragraph |
| `datum_summary` | `schema`, `kind`, `title`, `selected_document`, `readiness_status`, `source_files`, `warnings` | — | `_inspector_datum` | Definition list for the selected authoritative datum document plus diagnostic totals / warnings |
| `aws_read_only_surface` | `schema`, `kind`, `title`, `tenant_scope_id`, `mailbox_readiness`, `smtp_state`, `gmail_state`, `verified_evidence_state`, `selected_verified_sender`, `allowed_send_domains`, `write_capability`, `profile_summary` | `compatibility_warnings`, `inbound_capture`, `dispatch_health` | `_inspector_aws_read_only_surface` | Definition list + optional compatibility list |
| `aws_tool_error` | `schema`, `kind`, `title`, `error_code`, `error_message`, `warnings` | — | `_inspector_aws_tool_error` | Error card + warnings list |
| `narrow_write_form` | `schema`, `kind`, `title`, `read_only_context`, `submit_contract` | — | `_inspector_narrow_write_form` | Form + POST to `submit_contract.route` with schema and fixed fields |
| `csm_onboarding_form` | `schema`, `kind`, `title`, `read_only_context`, `submit_contract`, `onboarding_action_options` | — | `_inspector_csm_onboarding_form` | Select + `profile_id` + POST to `/portal/api/v2/admin/aws/csm-onboarding` using server-issued schema and fixed `tenant_scope` / `focus_subject` |
| `cts_gis_interface_panel` | `schema`, `kind`, `title`, `render_from_surface_payload`, `request_contract` | `warnings` | `build_admin_cts_gis_inspector` in `admin_cts_gis_runtime.py` | Dominant CTS-GIS Hanus lens surface with GeoJSON rendering, attention shell, intention controls, lens toggles, and concise operator focus, all driven from the canonical `surface_payload` |
| `network_summary` | `schema`, `kind`, `title`, `network_state`, `summary`, `notes` | `active_tab`, `portal_instance` | `_inspector_network` | Contract-first hosted/network summary with portal-instance and count overview |

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
