# Implementation Report: IDE Shell + Anthology Refactor

Date: 2026-03-12

Scope:

- `portals/mycite-le_fnd`
- `portals/mycite-le_tff`
- `portals/mycite-ne_mt`
- shared shell/runtime modules under `portals/_shared`

## Post-Implementation Audit (Sections 1-8)

1) Lock shell layout: implemented
- Shell regions are locked in each portal `portal/ui/templates/base.html`.
- Right inspector/drawer framework is present via `portal/ui/static/portal.js` + `portal/ui/static/portal.css`.

2) Lock route model: implemented
- Canonical service routes are present in each app: `/portal/system`, `/portal/network`, `/portal/utilities`, `/portal/peripherals`.
- `/portal` and legacy paths redirect to canonical routes.
- Activity bar model is centralized in `portals/_shared/portal/core_services/registry.py`.

3) Page behavior: implemented
- NETWORK, UTILITIES, PERIPHERALS, SYSTEM templates are present for all three portals.
- NETWORK uses alias/request-log/P2P selection model with right-inspector profile hook.
- PERIPHERALS exposes required 5-tab structure.

4) Right-side inspector framework: implemented
- Global inspector open/close/toggle/template APIs exist in `portal/ui/static/portal.js`.
- SYSTEM/NETWORK profile views and datum investigation integrate with right-side inspector behavior.

5) Data workbench shell + AITAS/NIMM: implemented
- Workbench centered on anthology table/graph with NIMM controls.
- AITAS facets are explicit in `data/engine/nimm/state.py`.
- Double-click datum investigation is routed to right inspector in `portal/ui/static/tools/data_tool.js`.

6) Anthology normalization: implemented with transitional fallback
- Canonical anthology runtime is `data/anthology.json`.
- NE_MT supports transitional read fallback to `data/demo-anthology.json` with warning in `data/storage_json.py`.
- Conspectus is no longer core runtime navigation dependency.

7) Daemon layer: implemented/formalized
- Daemon port contract now includes scoped actions, default focus, and output strategy in `data/engine/workspace.py`.
- API resolve endpoint reflects this contract in `portal/api/data_workspace.py`.

8) Extension points: implemented
- Shared runtime supports `private/tools.manifest.json` mount targets in `portals/_shared/portal/tools/runtime.py`.
- Mount targets are constrained to shell slots (`utilities`, `peripherals.tools`).

## 1. File-by-File Change Summary

Shared:

- `portals/_shared/portal/core_services/registry.py`
  - Canonical services: `network`, `utilities`, `peripherals`, `system`.
  - Canonical href mapping and legacy path activation mapping.
- `portals/_shared/portal/tools/runtime.py`
  - Added tool mount-target support and manifest loader (`private/tools.manifest.json`).

FND/TFF/NE_MT shell/UI:

- `portal/ui/templates/base.html`
  - Locked IDE shell regions and global right inspector container.
- `portal/ui/static/portal.css`
  - IDE shell layout styles + right-inspector styles + right-side overlay posture.
- `portal/ui/static/portal.js`
  - Global `window.PortalInspector` API and template-trigger wiring.
- `portal/ui/templates/services/network.html`
  - Alias/log/P2P workbench model + profile inspector trigger.
- `portal/ui/templates/services/utilities.html`
  - Utilities host page (`Inbox`, `Launchers`).
- `portal/ui/templates/services/peripherals.html`
  - Required tabs (`Tools`, `Peripherals`, `Progeny`, `Configuration`, `Vault`).
- `portal/ui/templates/services/system.html`
  - SYSTEM splash + embedded data workbench + profile inspector trigger.

Portal apps:

- `portals/mycite-le_fnd/app.py`
- `portals/mycite-le_tff/app.py`
- `portals/mycite-ne_mt/app.py`
  - Canonical service routes and compatibility redirects.
  - Page-aware context sidebar sections.
  - Switch-active-portal footer action context.

Data workbench/API:

- `portals/mycite-le_fnd/data/engine/workspace.py`
- `portals/mycite-le_tff/data/engine/workspace.py`
- `portals/mycite-ne_mt/data/engine/workspace.py`
  - Formalized daemon contract and scoped action enforcement.
  - Model metadata updated with AITAS + pattern-recognition scaffold status.
- `portals/*/data/engine/nimm/state.py`
  - Explicit AITAS state facets retained and synchronized.
- `portals/*/portal/api/data_workspace.py`
  - Daemon resolve API updated for focus/output contract fields.
- `portals/mycite-ne_mt/data/storage_json.py`
  - Anthology canonical path with transitional fallback to `demo-anthology.json`.

Data tool parity:

- `portals/*/portal/ui/static/tools/data_tool.js`
  - Double-click investigation opens right inspector summary.
- `portals/mycite-ne_mt/portal/ui/templates/tools/data_tool_home.html`
- `portals/mycite-ne_mt/portal/ui/templates/tools/partials/data_tool_shell.html`
  - Brought NE_MT data workbench template structure to parity.

Documentation:

- `docs/TOOLS_SHELL.md`
- `docs/DATA_TOOL.md`
- `docs/IMPLEMENTATION_REPORT_2026-03-12_IDE_SHELL_REFACTOR.md`

## 2. Route Summary

Canonical:

- `/portal` -> `/portal/system`
- `/portal/system`
- `/portal/network`
- `/portal/utilities`
- `/portal/peripherals`

Compatibility redirects:

- `/portal/home` -> `/portal/system`
- `/portal/data` and `/portal/data/<legacy>` -> `/portal/system`
- `/portal/tools` -> `/portal/peripherals?tab=tools`
- `/portal/inbox` -> `/portal/utilities?tab=inbox`
- `/portal/peripheral` -> `/portal/peripherals?tab=peripherals`
- `/portal/vault` -> `/portal/peripherals?tab=vault`
- `/portal/network/<legacy_tab>` -> mapped `view=alias|log|p2p`

## 3. Component/Layout Summary

Locked shell composition:

- Menu bar (visual-only)
- Activity bar (global services + session actions)
- Context sidebar (page-local)
- Workbench (primary content)
- Right inspector/drawer (collapsible, contextual)

Core shell is shared; page content and tool surfaces are mounted into shell regions.

## 4. Page-Behavior Summary

NETWORK:

- Left context separates aliases, request logs, and P2P channels.
- Selection updates workbench content.
- Portal profile/contact card opens in right inspector.

UTILITIES:

- Hosts utility-specific pages and launchers.
- Utility tools mount into `utilities` slot only.

PERIPHERALS:

- Required tabs implemented.
- Existing operational surfaces preserved and regrouped.
- Vault tab exposes KeePass path/contract-file boundary.

SYSTEM:

- Internal shell home context.
- Left sidebar profile-oriented.
- Workbench hosts data workbench.
- Detail views route to right-side inspector.

## 5. Data-Engine Summary

- Anthology remains primary interactive dataset.
- NIMM directives and AITAS facets are explicit state.
- Focus/investigation flow is modeled as:
  - select (focus)
  - investigate (inspector)
  - mediate (directive + AITAS context)
- Pattern-recognition expansion point remains scaffolded.

## 6. Anthology-Normalization Summary

- Canonical anthology file is `data/anthology.json`.
- Deterministic read/write ordering by layer/value_group/iteration is preserved.
- NE_MT transitional loader supports `demo-anthology.json` fallback with explicit deprecation warning.
- Runtime conceptus/conspectus dependency removed from core navigation flow.

## 7. Daemon-Layer Summary

Daemon port contract now includes:

- `port_id`
- `datum_ref`
- `allowed_actions`
- `default_focus` (`focus_source`, `focus_subject`)
- `output_strategy`

`daemon_port_resolve` now:

- validates action scope
- resolves focus defaults
- returns strategy-aware output payload

## 8. Remaining TODOs / Ambiguities

- No additional domain data was fabricated. Where source data is absent, pages render structured empty states.
- KeePass runtime integration remains boundary-only in this refactor (path/contracts surfaced, no new secret manager implementation added).
- Optional manifest adoption (`private/tools.manifest.json`) is supported; instance manifests must be authored per portal if mount overrides are needed.
