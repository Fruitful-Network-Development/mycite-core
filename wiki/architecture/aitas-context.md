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
- `Spacial`

Current implementation uses AITAS as a lightweight compatibility payload. The strongest live fields are:

- `attention`
- `intention`
- `spacial`

At present:

- file focus maps to `spacial = 1`
- datum focus maps to `spacial = 2`
- `time` is usually `null`
- `archetype` is partial and often placeholder

Canonical meaning comes from `attention` depth, not from `spacial` as a long-term field. The `spacial` name remains compatibility-readable because current runtime consumers still emit and consume it.

## Directional Intent

The long-term model should derive depth from the attention address and retire `spacial` as a canonical concept while preserving compatibility only as needed.

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
