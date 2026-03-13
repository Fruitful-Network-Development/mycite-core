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
- hosted payloads, including subject congregation metadata, broadcaster metadata, default progeny templates, and workflow/AWS callback metadata
- public profile/card payloads
- seed-file payloads for alias/profile/presentation scaffolding plus unified progeny instances

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

Materialization also normalizes `private/network/hosted.json` to the canonical `mycite.network.hosted.v2` shape and removes stale legacy `private/mycite-config-*.json` files that are not declared in the build spec.

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

## Hosted and progeny direction

`private/network/hosted.json` is now the canonical hosted metadata container for:

- subject congregation/workbench metadata
- broadcaster/people-tab metadata
- default progeny templates for `admin`, `member`, and `user`
- workflow and AWS callback metadata

Canonical progeny instance storage direction:

- directory: `private/network/progeny/`
- filename pattern: `msn-<provider_msn_id>.<progeny_type>-<alias_associated_msn_id>.json`

Legacy typed progeny directories remain read-compatible in runtime helpers, but build capture/materialize now favors the single-directory model.

## Example portal note

The example portal is currently materialized into:

- `/srv/compose/portals/state/example_portal`

Its anthology remains state-owned at:

- `/srv/compose/portals/state/example_portal/data/anthology.json`

For now the example portal uses the shared `tff` runtime flavor to preserve the familiar workshop UI. Its anthology remains state-owned and is not overwritten by repo materialization.
