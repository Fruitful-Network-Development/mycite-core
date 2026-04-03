# AITAS Context

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Architecture](README.md)

## Status

Supporting

## Parent Topic

[Architecture](README.md)

## Current Contract

AITAS is the shared context strip and payload vocabulary used by the unified `SYSTEM` workbench:

- `Attention`
- `Intention`
- `Time`
- `Archetype`
- `Spatial`

Current implementation uses AITAS as a lightweight compatibility payload. The strongest live canonical fields are:

- `attention`
- `intention`
- `spatial`

At present:

- file focus maps to spatial file context
- datum focus maps to spatial datum context
- `time` is usually `null`
- `archetype` is partial and often placeholder

Canonical meaning comes from `attention` depth, not from `spatial` as a long-term field. The typo'd `spacial` name remains compatibility-readable only as an input alias and, where still needed, a response projection for older clients.

## Directional Intent

The long-term model should derive depth from the attention address and retire `spacial` entirely once remaining compatibility consumers are gone.

## Boundaries

This page explains the AITAS compatibility layer. It does not define:

- the full `SYSTEM` state machine
- archetype resolution logic in depth
- time mediation semantics
- MSS or SAMRAS data structures

## Authoritative Paths / Files

- `docs/AITAS_CONTEXT_MODEL.md`
- `docs/development_declaration_state_machine.md`
- `portals/_shared/portal/data_engine/aitas_context.py`

## Source Docs

- `docs/AITAS_CONTEXT_MODEL.md`
- `docs/development_declaration_state_machine.md`
- `docs/directive_context_UI_refactor.md`

## Update Triggers

- Changes to the emitted AITAS payload
- Changes to file-focus versus datum-focus context
- Progress on retiring or renaming `spacial`
- New live use of `time` or `archetype` fields in the shell
