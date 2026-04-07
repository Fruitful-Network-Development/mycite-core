# mycite-core

Canonical source for the MyCite portal core, shared runtime, tool modules, and product documentation.

## Runtime Boundaries

- Repo code lives under `/srv/repo/mycite-core`
- Live instance state lives under `/srv/mycite-state/instances/<instance_id>/`
- Portal runtime is file-backed; there is no application database in the portal core
- Native runtime is systemd-first for live FND and TFF portals; `/srv/compose/portals/` is now limited to auth-support infrastructure and transitional host files

## Canonical Authority

- `private/config.json` controls tool exposure, mount target, and utility collection selection
- `private/utilities/tools/<tool>/` holds non-datum tool specs, profile JSON, audit files, and other tool-local utility data
- `data/sandbox/<tool>/` is the authoritative tool datum root
- `data/payloads/*.bin` and `data/payloads/cache/*.json` are the only binary and decoded-payload authority roots
- Tool code does not live in instance state; canonical tool code lives in [`packages/tools/`](packages/tools)

## Repository Layout

- `instances/_shared/` shared portal and runtime code
- `instances/deployed/` repo-tracked deployed instance mirrors
- `instances/convention/` convention/reference instance artifacts
- `instances/scripts/` capture/materialization helpers
- `packages/tools/` standalone tool modules and state adapters
- `packages/core/` core data-engine and related packages
- `docs/wiki/` maintained product and architecture documentation
- `docs/plans/` active planning documents

## Key Entry Points

- Shared portal logic: `instances/_shared/portal/**`
- Flavor runtime composition: `instances/_shared/runtime/flavors/*`
- Tool build/runtime contracts: `packages/tools/_shared/**`
- Portal build script: `python3 instances/scripts/portal_build.py`

## Canonical Docs

- [`docs/ownership-boundary.md`](docs/ownership-boundary.md)
- [`docs/wiki/README.md`](docs/wiki/README.md)
- [`docs/wiki/architecture/system-state-machine.md`](docs/wiki/architecture/system-state-machine.md)
- [`docs/wiki/data-model/datum-identity-and-resolution.md`](docs/wiki/data-model/datum-identity-and-resolution.md)
- [`docs/wiki/runtime-build/portal-config-model.md`](docs/wiki/runtime-build/portal-config-model.md)
- [`docs/wiki/tools/time-address-schema.md`](docs/wiki/tools/time-address-schema.md)
- [`docs/wiki/tools/internal-file-sources.md`](docs/wiki/tools/internal-file-sources.md)
- [`docs/plans/tool_dev.md`](docs/plans/tool_dev.md)

## Working Rule

Update repo code and docs first. Materialize or migrate state only through controlled scripts or explicit operational changes. Do not treat hidden compatibility paths, compose-state symlinks, or ad hoc runtime copies as equal-truth sources.
