# Service Shell Standard

## Current shell contract

Active portals use one shared shell composed of:

- top menu bar
- activity bar
- left context sidebar
- central workbench
- right inspector column

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

## Activity bar

Primary service entries are:

- `SYSTEM`
- `NETWORK`
- `UTILITIES`

FND adds compact activity-bar shortcuts for its enabled organization tools. Those shortcuts are derived from the materialized tool state, not from hard-coded shell forks.

## Use vs configure

- **Activity bar tool entries** (icons below SYSTEM / NETWORK / UTILITIES): each links to the tool’s **home** (`home_path`, e.g. `/portal/tools/agro_erp/home`). Purpose: **use** the tool (e.g. view AGRO ERP taxonomy, run tool features). The shell treats the current context as that tool (tool highlighted in activity bar, tool-use sidebar).
- **Utilities → Tools tab**: purpose is **configure / manage** tools (which tools are enabled, mount targets, etc.). Not the place to “run” a tool; use the activity bar to open the tool home.
- **`/portal/tools`** (no tool id): redirects to `/portal/utilities?tab=tools` (configuration).

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
