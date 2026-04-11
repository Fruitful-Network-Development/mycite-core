# Write Pipeline

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Data Model](README.md)

## Status

Canonical

## Parent Topic

[Data Model](README.md)

## Current Contract

Semantic writes should flow through shared preview and apply services instead of low-level append logic whenever the operation depends on field contracts, geometry templates, or resource adaptation.

Canonical shared routes include:

- `GET /portal/api/data/write/field_contracts`
- `POST /portal/api/data/write/preview`
- `POST /portal/api/data/write/apply`
- `POST /portal/api/data/geometry/preview`
- `POST /portal/api/data/geometry/apply`

The write pipeline owns:

- field-contract validation
- datum family semantics
- target ref-surface canonicalization
- deterministic ordering of writes
- explicit created-versus-reused summaries
- pass-through reporting of `contract_mss_sync` when anthology mutation requires contract recompilation

Within `SYSTEM`, write behavior still differs by file policy:

- `anthology.json` uses direct anthology authority for its local mutation path
- `samras-txa.json` and `samras-msn.json` use staged mutate and publish behavior

The important rule is that write-policy differences are capability differences, not separate user-facing shells.

## Boundaries

This page owns preview/apply semantics and write-policy framing. It does not own:

- rule-policy classification details
- MSS contract wire format
- hosted profile-card payloads
- SAMRAS structural encoding logic

## Authoritative Paths / Files

- `docs/CANONICAL_DATA_ENGINE.md`
- `instances/_shared/portal/data_engine/write_pipeline.py`
- `instances/_shared/portal/data_engine/field_contracts.py`
- `instances/_shared/portal/data_engine/geometry_datums.py`

## Source Docs

- `docs/CANONICAL_DATA_ENGINE.md`
- `docs/DATA_TOOL.md`
- `docs/NETWORK_PAGE_MODEL.md`
- `docs/AGRO_ERP_TOOL.md`

## Update Triggers

- Changes to preview/apply route contracts
- Changes to field contract or geometry template ownership
- Changes to `contract_mss_sync` behavior
- Changes to anthology versus staged publish write policy
