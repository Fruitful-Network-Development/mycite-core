# mycite-core

Canonical source for the live MyCite portal shell and its authoritative
documentation tree.

## Runtime Boundaries

- V2 repo code lives under `/srv/repo/mycite-core/MyCiteV2`
- preserved deployment snapshots live under `/srv/repo/mycite-core/deployed`
- Live instance state lives under `/srv/mycite-state/instances/<instance_id>/`
- Portal runtime is file-backed; there is no application database in the portal core

## Portal Architecture

- one portal shell
- canonical public entry: `/portal` -> `/portal/system`
- one runtime envelope family
- root surfaces: `SYSTEM`, `NETWORK`, `UTILITIES`
- `SYSTEM` owns the core datum-file workbench for the system sandbox
- fresh `SYSTEM` entry focuses the anchor file `anthology.json`
- `NETWORK` owns the read-only portal-instance system-log workbench backed by `data/system/system_log.json`
- `NETWORK` is not a tool and not a sandbox; contract correspondence is a filter over the same workbench
- canonical shell endpoint: `POST /portal/api/v2/shell`
- canonical tool work pages: `/portal/system/tools/<tool_slug>`
- utilities/configuration pages: `/portal/utilities/*`

## Key Entry Points

- V2 portal host: `MyCiteV2/instances/_shared/portal_host/app.py`
- V2 runtime catalog: `MyCiteV2/instances/_shared/runtime/runtime_platform.py`
- V2 shell runtime: `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- V2 shell contract: `MyCiteV2/packages/state_machine/portal_shell/shell.py`
- archived snapshot material: `deployed/README.md`

## Canonical Docs

- [`docs/README.md`](docs/README.md)
- [`docs/contracts/portal_shell_contract.md`](docs/contracts/portal_shell_contract.md)
- [`docs/contracts/route_model.md`](docs/contracts/route_model.md)
- [`docs/contracts/surface_catalog.md`](docs/contracts/surface_catalog.md)
- [`docs/plans/one_shell_portal_refactor.md`](docs/plans/one_shell_portal_refactor.md)
