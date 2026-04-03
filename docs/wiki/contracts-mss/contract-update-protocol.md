# Contract Update Protocol

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Contracts And MSS](README.md)

## Status

Supporting

## Parent Topic

[Contracts And MSS](README.md)

## Current Contract

Contract update flow is revisioned. The contract file remains the authoritative state, while the request log carries evidence for external update exchange.

Intended update operations include:

- `replace_snapshot`
- `add_entry`
- `update_entry`
- `remove_entry`
- `recompile`
- `acknowledge_revision`

An update message carries at least:

- `contract_id`
- `from_revision`
- `to_revision`
- `changed_paths`
- `change_type`
- `source_msn_id`
- `target_msn_id`
- `ts_unix_ms`

Request-log usage is narrow:

- use it for external sends, receives, and acknowledgements
- do not use it for local-only contract edits
- do not use it for local tool CRUD or local anthology writes

## Boundaries

This page owns revisioned contract-update messaging. It does not own:

- raw compact-array encoding
- semantic datum identity rules
- local audit-log behavior outside the contract-update boundary
- hosted session model

## Authoritative Paths / Files

- `docs/CONTRACT_UPDATE_PROTOCOL.md`
- contract API surfaces under `portals/_shared/portal/**`

## Source Docs

- `docs/CONTRACT_UPDATE_PROTOCOL.md`
- `docs/REQUEST_LOG_V1.md`
- `docs/HOSTED_SESSIONS.md`

## Update Triggers

- Changes to revision handling
- Changes to request-log usage boundaries
- Changes to external apply-update payload expectations
- Changes to optional relationship, access, or sync mode fields
