# Canonical Data Artifacts

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Data Model](README.md)

## Status

Canonical

## Parent Topic

[Data Model](README.md)

## Current Contract

The portal runtime is file-backed. Current canonical data artifacts include:

- `data/anthology.json`
- `data/samras-txa.json`
- `data/samras-msn.json`
- `data/resources/local/*.json`
- `data/resources/inherited/<source_msn_id>/*.json`
- `data/resources/index.local.json`
- `data/resources/index.inherited.json`
- `data/presentation/datum_icons.json`
- network and request-log state under `private/network/**`

For the current `SYSTEM` workbench, the visible file-focused surface is the root trio:

- `anthology.json`
- `samras-txa.json`
- `samras-msn.json`

Anthology loading uses a base-plus-overlay model:

- repo base: `anthology-base.json`
- portal state overlay: `data/anthology.json`
- merged runtime view in shared core

Resource registries remain engine-owned inventory and capability artifacts. They are not the visible `SYSTEM` tab model.

Presentation sidecars remain separate from anthology semantics. Current portal presentation metadata includes:

- `data/presentation/datum_icons.json`

Icon assignments are presentation-only state and do not alter anthology structure, rules, or datum identity.

## Boundaries

This page defines canonical runtime artifacts and ownership boundaries. It does not define:

- semantic datum identity rules in detail
- MSS contract wire shape
- SAMRAS structural validity
- hosted layout payloads

## Authoritative Paths / Files

- `docs/CANONICAL_DATA_ENGINE.md`
- `anthology-base.json`
- `instances/_shared/portal/data_engine/anthology_registry.py`
- `instances/_shared/portal/data_engine/anthology_overlay.py`

## Source Docs

- `docs/CANONICAL_DATA_ENGINE.md`
- `docs/DATA_TOOL.md`
- `docs/RESOURCE_STORAGE_CONVENTIONS.md`
- `docs/ANTHOLOGY_BASE_OVERLAY.md`

## Update Triggers

- Changes to the canonical file set
- Changes to anthology base-overlay merge behavior
- Changes to resource inventory location or ownership
- Changes to which artifacts are visible in `SYSTEM`
