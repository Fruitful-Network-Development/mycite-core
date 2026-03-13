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

Compatibility redirects remain:

- `/portal/home` -> `/portal/system`
- `/portal/data` -> `/portal/system`
- `/portal/tools` -> `/portal/utilities?tab=tools`
- `/portal/inbox` -> `/portal/network?tab=messages&kind=log&id=request_log`
- `/portal/peripheral` -> `/portal/utilities?tab=peripherals`

## Activity bar

Primary service entries are:

- `SYSTEM`
- `NETWORK`
- `UTILITIES`

FND adds compact activity-bar shortcuts for its enabled organization tools. Those shortcuts are derived from the materialized tool state, not from hard-coded shell forks.

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

## Inspector model

Global inspector runtime is provided by `portal/ui/static/portal.js` (`window.PortalInspector`).

Pages may:

- open contextual cards/templates
- show selected alias/member detail
- move datum editing into the right inspector instead of overlaying the workbench

## Extension rule

Tools consume shell slots and core APIs. They do not define alternate shells or alternate top-level route models.
