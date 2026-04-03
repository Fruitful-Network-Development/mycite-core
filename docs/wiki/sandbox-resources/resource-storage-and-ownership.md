# Resource Storage And Ownership

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Sandbox And Resources](README.md)

## Status

Canonical

## Parent Topic

[Sandbox And Resources](README.md)

## Current Contract

Resource storage is intentionally split by owner:

- `data/anthology.json` for canonical local datum state
- `data/resources/local/*.json` for isolated local resources
- `data/resources/inherited/<source_msn_id>/*.json` for cached foreign snapshots
- `data/resources/index.local.json` for local inventory
- `data/resources/index.inherited.json` for inherited inventory

Sandbox is the lifecycle service for local resources. It is not the canonical cross-scope inventory owner.

Compatibility read note:

- authored legacy files at `data/resources/rec.*.json` are surfaced for read paths as `legacy_root` entries while migration to `data/resources/local/*.json` is staged.

Resource payloads should carry:

- `schema`
- `resource_id`
- `resource_kind`
- `scope`
- `source_msn_id`
- `version_hash`
- `updated_at`
- `anthology_compatible_payload`

SAMRAS-specific storage rules still apply within this ownership model:

- structural rows normalize through the shared-core SAMRAS package
- persisted structural magnitudes must be canonical bitstreams
- legacy human-authored SAMRAS forms are migration/read compatibility only

## Boundaries

This page owns storage ownership and file-shape expectations. It does not own:

- sandbox lifecycle behavior in depth
- contract MSS context
- visible `SYSTEM` shell behavior
- SAMRAS validity predicates in full detail

## Authoritative Paths / Files

- `docs/RESOURCE_STORAGE_CONVENTIONS.md`
- `portals/_shared/portal/data_engine/resource_registry.py`
- `portals/_shared/portal/samras/`

## Source Docs

- `docs/RESOURCE_STORAGE_CONVENTIONS.md`
- `docs/SANDBOX_ENGINE.md`

## Update Triggers

- Changes to local or inherited resource paths
- Changes to resource JSON shape
- Changes to inventory ownership
- Changes to SAMRAS persistence normalization inside resource payloads
