# Portals Directory

`portals/` contains active portal runtimes, shared runtime modules, shared assets, and portal build/update tooling.

## Active runtimes

- `mycite-le_fnd`
- `mycite-le_tff`

Retired from active scope:

- `mycite-ne_mt`

Directories without an app/runtime surface should not be treated as active portal implementations.

## Shared runtime

- `_shared/` shared core-service, network, data-engine, and tool-loading modules
- `assets/` shared icons and UI assets
- `scripts/portal_build.py` capture/materialize workflow for portal build specs

## Build-spec workflow

Each active portal carries a repo-owned `build.json`:

- `mycite-le_fnd/build.json`
- `mycite-le_tff/build.json`

Those specs materialize the live state files the runtime reads:

- `private/config.json`
- legacy-compatible `private/mycite-config-*.json`
- `private/network/hosted.json`
- `private/tools.manifest.json`
- public profile cards
- optional seed files under `private/network/*` and related progeny/profile trees

Anthology is intentionally not generated in this phase.

## Canonical docs

- [`../README.md`](../README.md)
- [`../docs/PORTAL_BUILD_SPEC.md`](../docs/PORTAL_BUILD_SPEC.md)
- [`../docs/TOOLS_SHELL.md`](../docs/TOOLS_SHELL.md)
- [`../docs/CANONICAL_DATA_ENGINE.md`](../docs/CANONICAL_DATA_ENGINE.md)
- [`../docs/NETWORK_PAGE_MODEL.md`](../docs/NETWORK_PAGE_MODEL.md)
