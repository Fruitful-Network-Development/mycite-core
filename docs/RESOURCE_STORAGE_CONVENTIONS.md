# Resource Storage Conventions

## Ownership model

Resource storage is intentionally split by owner:

- `data/anthology.json` -> canonical local datum state
- `data/resources/local/*.json` -> isolated local resources
- `data/resources/inherited/<source_msn_id>/*.json` -> cached foreign resource snapshots
- `data/resources/index.local.json` -> local inventory index
- `data/resources/index.inherited.json` -> inherited inventory index

Sandbox remains the lifecycle service (draft/edit/compile/publish) for local resources. It is not the canonical cross-scope inventory owner.

## Naming

Local resource files:

- `data/resources/local/<resource_name>.json`

Inherited resource files:

- `data/resources/inherited/<source_msn_id>/<resource_name>.json`

Initial migrated SAMRAS resource names:

- `samras.txa.json`
- `samras.msn.json`

## Internal IDs

Local:

- `local:samras.txa`
- `local:samras.msn`

Inherited:

- `foreign:<source_msn_id>:samras.txa`
- `foreign:<source_msn_id>:samras.msn`

## Resource file shape

Each resource JSON should include:

- `schema`
- `resource_id`
- `resource_kind`
- `scope` (`local` or `inherited`)
- `source_msn_id`
- `version_hash`
- `updated_at`
- `anthology_compatible_payload`

Optional lifecycle fields:

- `draft_metadata`
- `compile_metadata`
- `publish_metadata`
- `sync_metadata` (for inherited snapshots)

## Anthology-compatible payload normalization

When writing `anthology_compatible_payload`, shared-core normalization applies:

- one datum per line in compact payload
- deterministic identifier ordering
- per `(layer, value_group)` iterations start at `1` and are contiguous

These rules are implemented in `portals/_shared/portal/data_engine/resource_registry.py`.

For SAMRAS structural rows (`reference == 0-0-5`):

- writes normalize through the canonical shared-core SAMRAS package (`portals/_shared/portal/samras/`)
- persisted structural magnitudes must be canonical bitstreams
- numeric-hyphen and other legacy SAMRAS forms are migration/read compatibility only
- address rows are derived from the governing structure and must not outrun it
- raw SAMRAS magnitude authoring is not the normal long-term editing authority
