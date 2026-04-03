# Datum Identity And Resolution

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Data Model](README.md)

## Status

Canonical

## Parent Topic

[Data Model](README.md)

## Current Contract

Datum resolution uses canonical datum paths as semantic identity. Implementations must not treat row order, MSS offsets, or storage-local addresses as the durable identity of a datum.

Canonical resolution order is:

1. local anthology
2. local projection or cache keyed by canonical path
3. compiled compact-array snapshot keyed by canonical path
4. public contact-card export
5. remote fetch or negotiated contract flow

Canonical network-facing refs use dot-qualified form:

- `<msn_id>.<datum>`

Storage-local layer/value-group/iteration addresses remain useful inside a specific anthology or MSS snapshot, but they are not the stable semantic address across recompiles.

Critical distinction:

- datum address (`layer-value_group-iteration`) is a local anthology/resource row address
- SAMRAS node addressing is a structural address model derived from SAMRAS breadth-first topology
- MSS compact-array indexing is transport-local to an isolated closure snapshot

These contexts are related by decode/resolve workflows but are not interchangeable identifiers.

The compiled datum index exists to preserve this separation:

- `datum_path` is the stable semantic key
- `storage_address` is snapshot-local
- `semantic_address` preserves original source address when available

## Boundaries

This page owns semantic identity and resolution order. It does not own:

- MSS wire encoding details
- contract revision protocol
- UI table behavior in `SYSTEM`
- sandbox resource lifecycle

## Authoritative Paths / Files

- `docs/CANONICAL_DATA_ENGINE.md`
- `docs/CONTRACT_COMPACT_INDEX.md`
- `portals/_shared/portal/data_engine/datum_identity.py`
- `portals/_shared/portal/services/public_datum_resolver.py`

## Source Docs

- `docs/CANONICAL_DATA_ENGINE.md`
- `docs/CONTRACT_COMPACT_INDEX.md`
- `docs/MSS_COMPACT_ARRAY_SPEC.md`
- `docs/AGRO_ERP_TOOL.md`

## Update Triggers

- Changes to canonical path parsing or normalization
- Changes to resolution precedence
- Changes to dot-qualified reference policy
- Changes to how compiled contract entries preserve semantic identity
