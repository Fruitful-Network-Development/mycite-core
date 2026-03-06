# Portals Directory

`portals/` contains MyCite portal instances and examples.

## Active app instances

These directories include `app.py` and can run as Flask portal apps:

- `mycite-ne-example`
- `mycite-le-example`
- `mycite-le_fnd`
- `mycite-le_cvcc`
- `mycite-ne_mw`
- `mycite-ne_dm`

## State-only profile folders

These directories are profile/state folders (no local app entrypoint):

- `mycite-le_tff`
- `mycite-ne_mt`

## Shell/runtime standard

All active portals must follow the shared service-shell/runtime contract:

- shared service runtime: `../portals/_shared/portal/core_services/`
- shared tool runtime: `../portals/_shared/portal/tools/runtime.py`
- contract doc: [`../docs/TOOLS_SHELL.md`](../docs/TOOLS_SHELL.md)

## Canonical docs

- [`../README.md`](../README.md)
- [`../docs/DEVELOPMENT_PLAN.md`](../docs/DEVELOPMENT_PLAN.md)
- [`../docs/DOCUMENTATION_POLICY.md`](../docs/DOCUMENTATION_POLICY.md)
- [`../docs/request_log_and_contracts.md`](../docs/request_log_and_contracts.md)
- [`../docs/DATA_TOOL.md`](../docs/DATA_TOOL.md)
- [`../docs/DATA_TOOL_ICONS.md`](../docs/DATA_TOOL_ICONS.md)
