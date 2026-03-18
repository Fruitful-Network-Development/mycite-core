# Inherited Resource Contract Module

## Purpose

`portals/_shared/portal/data_engine/inherited_contract_resources.py` is the shared-core subscription/sync layer for inherited resources.

It keeps responsibilities explicit:

- contracts track subscription/sync metadata
- inherited snapshots are stored as files under `data/resources/inherited/...`
- inventory is surfaced by `data/resources/index.inherited.json`

Contracts are not the storage owner of full inherited payloads.

## Contract-tracked metadata

Per tracked inherited resource:

- `source_msn_id`
- `contract_id`
- `resource_id`
- `resource_name`
- `version_hash`
- `last_sync_unix_ms`
- `next_poll_unix_ms`
- `status`

These fields are persisted on contract payloads under `inherited_resource_sync`.

## Refresh flow

Refresh endpoints are exposed on shared data routes:

- `POST /portal/api/data/resources/inherited/refresh`
- `POST /portal/api/data/resources/inherited/refresh_source`
- `POST /portal/api/data/resources/inherited/disconnect_source`
- `GET /portal/api/data/resources/inherited/subscriptions`

Refresh behavior:

1. resolve source/contract
2. fetch via `ExternalResourceResolver`
3. persist snapshot into `data/resources/inherited/<source_msn_id>/<resource_name>.json`
4. update `index.inherited.json`
5. update contract subscription/sync metadata

## Resolver interaction

`SandboxEngine.resolve_inherited_resource_context` checks inherited cache files first (`scope = foreign_cached`) before requesting external fetch. This keeps inherited handling durable and inventory-driven.
