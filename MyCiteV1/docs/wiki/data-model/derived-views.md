# Derived Views

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Data Model](README.md)

## Status

Supporting

## Parent Topic

[Data Model](README.md)

## Current Contract

Derived workbench views remain secondary projections over canonical data rather than separate data authorities.

Current derived-view contracts include:

- anthology graph extraction
- datum icon presentation sidecars

Anthology graph extraction is anthology-authoritative:

- one anthology row becomes one graph node
- edges are derived from anthology references
- focus and context are view parameters, not separate stored graph state

Current graph API:

- `GET /portal/api/data/anthology/graph`

Presentation-sidecar icon mapping is stored separately from anthology semantics:

- global icon library under `assets/icons/**`
- per-portal sidecar under `data/presentation/datum_icons.json`

Icon assignment flows through directive and commit behavior rather than direct template filesystem scans.

## Boundaries

This page owns derived graph and presentation view rules. It does not own:

- anthology semantic identity
- shell directive definitions
- sandbox lifecycle
- hosted or contract resolution behavior

## Authoritative Paths / Files

- anthology graph view logic under shared portal data-engine workbench code
- `data/presentation/datum_icons.json`
- shared icon and directive routes under `instances/_shared/portal/api/data_workspace.py`

## Source Docs

- `docs/ANTHOLOGY_GRAPH_EXTRACTION_MODEL.md`
- `docs/DATA_TOOL_ICONS.md`

## Update Triggers

- Changes to graph node or edge derivation
- Changes to graph focus/context parameters
- Changes to icon-sidecar schema or directive behavior
- Changes to how derived view models are exposed to the workbench
