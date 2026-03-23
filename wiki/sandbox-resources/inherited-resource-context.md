# Inherited Resource Context

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Sandbox And Resources](README.md)

## Status

Canonical

## Parent Topic

[Sandbox And Resources](README.md)

## Current Contract

Inherited resource context is resolved through shared sandbox and data-engine behavior rather than through a separate visible `SYSTEM` interaction model.

Relevant shared routes include:

- `POST /portal/api/data/sandbox/inherited/resolve`
- `POST /portal/api/data/sandbox/inherited/compile_txa`
- `POST /portal/api/data/sandbox/inherited/adapt_txa`
- `POST /portal/api/data/resources/inherited/refresh`
- `POST /portal/api/data/resources/inherited/refresh_source`
- `POST /portal/api/data/resources/inherited/disconnect_source`

Current MVP boundary for AGRO and related inherited-write flows is:

1. load isolated source resource
2. compile or adapt inherited context
3. expose stable field-usable refs
4. feed those refs into shared write preview and apply

No full foreign txa tree should be materialized back into local anthology during these flows.

Contracts track inherited-resource subscription and sync metadata rather than owning the full payload storage. Current tracked metadata includes:

- `source_msn_id`
- `contract_id`
- `resource_id`
- `resource_name`
- `version_hash`
- `last_sync_unix_ms`
- `next_poll_unix_ms`
- `status`

Refresh behavior remains:

1. resolve source and contract
2. fetch via the external resource resolver
3. persist the inherited snapshot under `data/resources/inherited/<source_msn_id>/`
4. update inherited indexes
5. update contract subscription and sync metadata

Inherited context resolution is cache-aware. Sandbox checks inherited cache files first before requesting a new external fetch.

## Boundaries

This page owns inherited resource adaptation and refresh framing. It does not own:

- NETWORK contract-edit semantics
- generic sandbox stage/save flow
- local anthology identity rules
- hosted session layout

## Authoritative Paths / Files

- `docs/SANDBOX_ENGINE.md`
- `docs/CANONICAL_DATA_ENGINE.md`
- `portals/_shared/portal/sandbox/engine.py`
- `portals/_shared/portal/data_engine/inherited_contract_resources.py`

## Source Docs

- `docs/SANDBOX_ENGINE.md`
- `docs/CANONICAL_DATA_ENGINE.md`
- `docs/AGRO_ERP_TOOL.md`
- `docs/INHERITED_RESOURCE_CONTRACT_MODULE.md`

## Update Triggers

- Changes to inherited resolve or adapt route contracts
- Changes to refresh and disconnect semantics
- Changes to how inherited contexts feed write preview/apply
- Changes to local materialization boundaries for foreign resource data
