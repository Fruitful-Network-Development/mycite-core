# External Resource Isolates

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Data Model](README.md)

## Status

Canonical

## Parent Topic

[Data Model](README.md)

## Current Contract

External resource isolates support public resource acquisition from remote contact cards without requiring full remote anthology import.

This subsystem is separate from contract context:

- contracts remain canonical for relationship-scoped MSS context
- public resources are normalized into isolate bundles for engine-side reasoning

Three identities are tracked at all times:

1. local anthology ref
2. isolated semantic identity
3. origin and provenance identity

Contact cards may expose `public_resources[]` descriptors with fields such as:

- `resource_id`
- `kind`
- `export_family`
- `href`
- `lens_hint`
- availability metadata

Fetched resources are normalized into isolate bundles that preserve source identity, export family, wire variant, closure metadata, and normalized datum entries.

Sparse local materialization remains planner-driven. Tools submit intent and the shared engine returns an ordered plan for:

- prerequisites already local
- isolate-bundle refs that can be materialized
- missing prerequisites that may be auto-created
- ordered target writes

## Boundaries

This page owns public resource isolate handling. It does not own:

- relationship-scoped contract MSS context
- local anthology semantic identity
- hosted alias shell behavior
- tool-specific UI flows

## Authoritative Paths / Files

- `instances/_shared/portal/data_engine/external_resources/`
- shared `/portal/api/data/external/*` endpoints

## Source Docs

- `docs/EXTERNAL_RESOURCE_ISOLATES.md`
- `docs/CANONICAL_DATA_ENGINE.md`

## Update Triggers

- Changes to isolate descriptor shape
- Changes to provenance or identity tracking
- Changes to external fetch or plan-materialization endpoints
- Changes to the boundary between public isolates and contract context
