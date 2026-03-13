# Portal Build Spec

## Purpose

Each active portal now carries a repo-owned `build.json` used to materialize the live file-backed portal state.

Active specs:

- `portals/mycite-le_example/build.json`
- `portals/mycite-le_fnd/build.json`
- `portals/mycite-le_tff/build.json`

## Phase-1 authority

`build.json` is authoritative for:

- runtime flavor selection metadata
- portal identity metadata
- enabled optional tools
- tool mount targets
- canonical private config payload
- legacy-compatible private config payloads
- hosted payloads
- public profile/card payloads
- seed-file payloads for alias/progeny/profile/presentation scaffolding

Not authoritative yet:

- anthology content
- runtime request logs
- vault key material
- admin/runtime action logs

## Commands

Capture current source/state into build specs:

```bash
python3 portals/scripts/portal_build.py capture
```

Materialize build specs into live state:

```bash
python3 portals/scripts/portal_build.py materialize
```

Single portal variants are also supported:

```bash
python3 portals/scripts/portal_build.py capture mycite-le_fnd
python3 portals/scripts/portal_build.py materialize mycite-le_tff
python3 portals/scripts/portal_build.py materialize mycite-le_example
```

## Materialized outputs

Materialization writes only the state files the runtime expects for portal-specific behavior:

- `private/config.json`
- `private/mycite-config-*.json`
- `private/network/hosted.json`
- `private/tools.manifest.json`
- public profile cards
- declared seed payloads under `private/network/*`, `private/utilities/vault/*`, and `data/presentation/*`

It does not overwrite `data/anthology.json`.

## Tool policy

- `data_tool` is recorded as a core SYSTEM surface, not an optional packaged tool
- retired/demo tools should not appear in `tools.enabled`
- `private/tools.manifest.json` is generated from `build.json`

## Source-of-truth boundary

Repo build specs author portal-specific instance configuration.

Live state remains the runtime source actually mounted into containers.

## Shared runtime direction

The repo is moving toward a builder/runtime split:

- shared executable runtime: `portals/runtime/`
- shared flavor runtimes: `portals/_shared/runtime/flavors/*`
- per-portal directories (`mycite-le_fnd`, `mycite-le_tff`, `mycite-le_example`) reduced toward spec-only ownership

This means portal-specific state/config/profile/tool selections live in `build.json`, while executable code lives in the shared runtime tree.

## Example portal note

The example portal is currently materialized into:

- `/srv/compose/portals/state/example_portal`

Its anthology remains state-owned at:

- `/srv/compose/portals/state/example_portal/data/anthology.json`

For now the example portal uses the current TFF runtime flavor to preserve the familiar workshop UI, but it should get its own demo MSN/key/domain before public exposure.
