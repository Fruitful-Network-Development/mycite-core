# Build And Materialization

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Runtime And Build](README.md)

## Status

Canonical

## Parent Topic

[Runtime And Build](README.md)

## Current Contract

Each active portal carries a repo-owned `build.json` used to materialize live file-backed state.

`build.json` is authoritative for bootstrap inputs such as:

- portal identity metadata
- enabled tools and mounts
- private config payloads
- hosted payloads and progeny templates
- public profiles and cards
- network seed payloads

`build.json` is not the live runtime authority after materialization. Runtime authority moves to canonical file-backed artifacts and shared services.

Materialization writes expected runtime state such as:

- `private/config.json`
- `private/network/hosted.json`
- `private/network/contracts/*.json`
- public profile-card payloads
- declared seed files under `private/network/*`, `private/utilities/vault/*`, and `data/presentation/*`

Materialization does not overwrite `data/anthology.json`.

Canonical commands are:

- `python3 portals/scripts/portal_build.py capture`
- `python3 portals/scripts/portal_build.py materialize`

## Boundaries

This page owns build-spec authority and materialization boundaries. It does not own:

- live runtime semantics after materialization
- shell behavior
- contract compact-array wire rules
- local anthology mutation workflows

## Authoritative Paths / Files

- `docs/PORTAL_BUILD_SPEC.md`
- `portals/*/build.json`
- `portals/scripts/portal_build.py`

## Source Docs

- `docs/PORTAL_BUILD_SPEC.md`
- `README.md`
- `docs/HOSTED_SESSIONS.md`

## Update Triggers

- Changes to `build.json` authority
- Changes to capture or materialize commands
- Changes to what files are seeded or overwritten
- Changes to hosted, profile, or network seed responsibilities
