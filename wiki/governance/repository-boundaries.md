# Repository Boundaries

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Governance](README.md)

## Status

Canonical

## Parent Topic

[Governance](README.md)

## Current Contract

Repo code lives in `/srv/repo/mycite-core`. Live file-backed portal state lives under `/srv/mycite-state/instances/<instance_id>/`.

Transitional note:

- legacy compatibility symlinks may still exist under `/srv/compose/portals/state/<portal_instance>` while the host/runtime repo finishes dropping old path assumptions.

The portal runtime is file-backed. There is no application database in the portal runtime. Build specs materialize state, but live runtime behavior reads canonical state artifacts and shared services.

Working rule:

- update repo code and repo docs
- materialize state when needed
- rebuild the target runtime
- do not edit running runtime-state files directly

Repository policy also distinguishes between material that belongs in this repo and operational reporting owned elsewhere.

## Boundaries

This page owns repo-versus-live-state and documentation ownership boundaries. It does not own:

- build-spec field definitions in detail
- contract or sandbox semantics
- deployment procedures outside the repo-facing rule set
- commit hygiene beyond the high-level repo policy

## Authoritative Paths / Files

- `README.md`
- `wiki/README.md`
- `README.md`

## Source Docs

- `README.md`
- `docs/repo_policy.md`
- `docs/DOCUMENTATION_POLICY.md`

## Update Triggers

- Changes to repo versus live-state paths
- Changes to materialization workflow
- Changes to repo policy on what belongs here
- Changes to the "do not edit running container files directly" rule
