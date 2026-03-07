# Portals Directory

`portals/` is now intentionally minimal in this repository.

## In-repo portal instance

- `mycite-le_fnd` (active canonical portal implementation)

## Shared runtime/assets

- `_shared/` shared core-service and data-contract modules
- `assets/` shared icons and UI assets
- `scripts/` portal-adjacent helper scripts

## Archived one-off instances

Non-FND portal instance sources were removed from `mycite-core` and archived as runtime snapshots at:

- `/srv/compose/portals/unused_portal_sources/2026-03-07-fnd-only/`

Archived folders include:

- `mycite-le-example`
- `mycite-le_cvcc`
- `mycite-le_tff`
- `mycite-ne-example`
- `mycite-ne_dm`
- `mycite-ne_mt`
- `mycite-ne_mw`

## Shell/runtime standard

FND still follows the shared service-shell/runtime contract:

- shared service runtime: `../portals/_shared/portal/core_services/`
- shared tool runtime: `../portals/_shared/portal/tools/runtime.py`
- shell contract doc: [`../docs/TOOLS_SHELL.md`](../docs/TOOLS_SHELL.md)

## Canonical docs

- [`../README.md`](../README.md)
- [`../docs/DEVELOPMENT_PLAN.md`](../docs/DEVELOPMENT_PLAN.md)
- [`../docs/DOCUMENTATION_POLICY.md`](../docs/DOCUMENTATION_POLICY.md)
- [`../docs/request_log_and_contracts.md`](../docs/request_log_and_contracts.md)
- [`../docs/DATA_TOOL.md`](../docs/DATA_TOOL.md)
- [`../docs/TIME_SERIES_ABSTRACTION.md`](../docs/TIME_SERIES_ABSTRACTION.md)
