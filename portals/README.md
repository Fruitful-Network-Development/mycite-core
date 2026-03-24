# Portals Directory

`portals/` contains portal build specs, the shared runtime, shared assets, and portal build/update tooling.

## Active portal specs

- `mycite-le_example`
- `mycite-le_fnd`
- `mycite-le_tff`

Retired from active scope:

- `mycite-ne_mt`

These directories should be treated as portal specs, not standalone runtime roots.

## Shared runtime

- `runtime/` generic runtime image + app loader
- `_shared/` shared core-service, network, data-engine, and tool-loading modules
- `_shared/runtime/flavors/` flavor-specific runtime code (`fnd`, `tff`)
- `assets/` shared icons and UI assets
- `scripts/portal_build.py` capture/materialize workflow for portal build specs

## Build-spec workflow

Each active portal carries a repo-owned `build.json`:

- `mycite-le_example/build.json`
- `mycite-le_fnd/build.json`
- `mycite-le_tff/build.json`

Those specs materialize the live state files the runtime reads:

- `private/config.json`
- legacy-compatible `private/mycite-config-*.json`
- `private/network/hosted.json`
- `private/config.json -> tools_configuration` as the sole tool configuration authority
- `private/contracts/*.json`
- public profile cards
- optional seed files under `private/network/*`, `private/contracts/*`, and related progeny/profile trees

Legacy `private/tools.manifest.json` is retired. Materialization removes it if it is still present in a live target.

Anthology is intentionally not generated in this phase.

## Canonical docs

- [`../README.md`](../README.md)
- [`../wiki/runtime-build/build-and-materialization.md`](../wiki/runtime-build/build-and-materialization.md)
- [`../wiki/architecture/shell-and-page-composition.md`](../wiki/architecture/shell-and-page-composition.md)
- [`../wiki/data-model/canonical-data-artifacts.md`](../wiki/data-model/canonical-data-artifacts.md)
- [`../wiki/network-hosted/network-page-model.md`](../wiki/network-hosted/network-page-model.md)
