# Service Shell Standard

## Current shell contract

Active portals use one shared shell composed of:

- top menu bar
- activity bar
- left control panel
- central workbench
- right Details inspector column

The workbench viewport is the primary scroll region. Sidebars and the activity bar stay pinned to the shell frame.

## Canonical routes

- `GET /portal` -> `/portal/system`
- `GET /portal/system`
- `GET /portal/network`
- `GET /portal/utilities`
- `GET /portal/data` -> `/portal/tools/data_tool/home`

Compatibility redirects remain:

- `/portal/home` -> `/portal/system`
- `/portal/tools` -> `/portal/utilities?tab=tools`
- `/portal/inbox` -> `/portal/network?tab=messages&kind=log&id=request_log`
- `/portal/peripheral` -> `/portal/utilities?tab=peripherals`

`/portal/data/<path:tab_id>` also redirects to `/portal/tools/data_tool/home`.

For `SYSTEM`, the older split-view query framing has been removed from active routing. The shell now treats the unified workbench as the only current navigation surface.

Direct tool-home routes such as `/portal/tools/agro_erp/home` also remain reachable as hidden compatibility aliases only. The canonical user-facing launch path for mediated tools is now `SYSTEM` -> `Mediate`.

## Activity bar

Primary service entries are:

- `SYSTEM`
- `NETWORK`
- `UTILITIES`

Optional tools must not reintroduce separate activity-bar application entries. The visible activity bar is reserved for the three primary services above.

## Use vs configure

- **`SYSTEM` -> `Mediate`**: canonical place to discover and open compatible mediated tools for the current file or datum context.
- **Utilities -> Tools tab**: configure and manage tools (which tools are enabled, mount targets, etc.). It is not the canonical place to run a tool workflow.
- **`/portal/tools`** (no tool id): redirects to `/portal/utilities?tab=tools` (configuration).
- **`/portal/tools/<tool>/home`**: compatibility alias for direct access only. Do not frame this as the current shell model in docs or navigation.

## Tool runtime contract

Optional tools are loaded through the shared runtime:

- `portals/_shared/portal/tools/runtime.py`

Authoring source:

- per-portal `build.json`

Materialized runtime inputs:

- `private/config.json`
- `private/mycite-config-*.json` (legacy compatibility)
- `private/tools.manifest.json`

Rules:

- `data_tool` is a core SYSTEM surface, not an optional packaged tool
- the current `SYSTEM` contract is one unified workbench over `anthology.json`, `samras-txa.json`, and `samras-msn.json`
- mediated tools launch through the shared `SYSTEM` Mediate flow instead of defining alternate shell chrome
- missing `enabled_tools` in a real config means no optional tools are enabled
- package auto-discovery is only a fallback when no portal config exists

## Shared shell assets

Canonical shell static/template assets are served from the shared shell source under:

- `portals/_shared/runtime/flavors/fnd/portal/ui/templates`
- `portals/_shared/runtime/flavors/fnd/portal/ui/static`

Flavor runtimes compose this shared shell rather than maintaining duplicated copies.

## Inspector model

Global inspector runtime is provided by `portal/ui/static/portal.js` (`window.PortalInspector`).

Pages may:

- open contextual cards/templates
- show selected alias/member detail
- move datum editing into the right inspector instead of overlaying the workbench

## Extension rule

Tools consume shell slots and core APIs. They do not define alternate shells or alternate top-level route models.
