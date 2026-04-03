# Compiled Datum Index

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Contracts And MSS](README.md)

## Status

Canonical

## Parent Topic

[Contracts And MSS](README.md)

## Current Contract

The compiled datum index is the identity-keyed view of a contract's compact array. It exists so consumers resolve datums by canonical path rather than by storage order inside an isolated MSS snapshot.

The key idea is:

- `datum_path` is semantic identity
- `storage_address` is snapshot-local position
- `semantic_address` preserves source address when available

An index entry is keyed by canonical datum path such as `<msn_id>.<datum>`. Recompilation may change row order or storage-local identifiers, but the semantic key remains stable for consumers.

This derived view is what higher-level services should use for lookup and comparison when they work against contract context.

## Boundaries

This page owns the compiled index abstraction. It does not own:

- the raw MSS storage form
- contract handshake flow
- shell presentation of contract rows
- public hosted profile resolution

## Authoritative Paths / Files

- `docs/CONTRACT_COMPACT_INDEX.md`
- `portals/_shared/portal/data_engine/datum_identity.py`

## Source Docs

- `docs/CONTRACT_COMPACT_INDEX.md`
- `docs/MSS_COMPACT_ARRAY_SPEC.md`
- `docs/CANONICAL_DATA_ENGINE.md`

## Update Triggers

- Changes to compiled entry shape
- Changes to semantic path keying
- Changes to use of `source_identifier` or `semantic_address`
- Changes to how higher-level services consume compact-array snapshots
