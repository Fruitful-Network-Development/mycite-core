# MyCiteV2

MyCiteV2 is the live implementation root for the single MyCite portal shell.
The authoritative semantics live in [`../docs/`](../docs/README.md); this tree
is the code that serves and verifies that shell.

## What lives here

- `instances/_shared/portal_host/`
  The public V2 host, browser shell assets, and canonical `/portal` routes.
- `instances/_shared/runtime/`
  Shared runtime composition for `SYSTEM`, `NETWORK`, and `UTILITIES`.
- `packages/`
  Ports, adapters, state-machine logic, and cross-domain services.
- `tests/`
  Contract, integration, and architecture checks that keep the single-shell model stable.

## Working assumptions

- There is one portal shell.
- Public portal ingress is FND-only and enters through `/portal`.
- `SYSTEM` is the reducer-owned datum-file workbench.
- `NETWORK` is the read-only system-log workbench.
- `UTILITIES` owns exposure, integrations, and configuration surfaces.
- Archived deployment material belongs under `../deployed/` and is not runtime source.

## Read first

- [../docs/README.md](../docs/README.md)
- [../docs/contracts/portal_shell_contract.md](../docs/contracts/portal_shell_contract.md)
- [../docs/contracts/route_model.md](../docs/contracts/route_model.md)
- [../docs/contracts/surface_catalog.md](../docs/contracts/surface_catalog.md)
