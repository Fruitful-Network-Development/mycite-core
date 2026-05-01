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
- `scripts/`
  Operational entrypoints, including CTS-GIS compile/validate/deploy helpers.

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

## CTS-GIS Operations

- `scripts/compile_cts_gis_artifact.py`
  Rebuilds the compiled CTS-GIS artifact used by `production_strict`.
- `scripts/validate_cts_gis_sources.py`
  Validates the live `sources/` plus `sources/precincts/` layout and can require
  compiled-artifact fingerprint match.
- `scripts/deploy_portal_update.sh`
  Enforces compile-before-restart posture for FND unless explicitly skipped for
  diagnostic workflows.
