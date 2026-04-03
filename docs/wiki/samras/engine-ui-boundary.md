# Engine UI Boundary

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [SAMRAS](README.md)

## Status

Canonical

## Parent Topic

[SAMRAS](README.md)

## Current Contract

The engine owns SAMRAS semantics. UI surfaces consume structure-aware view models and mutation results.

Engine ownership includes:

- decode and encode
- structural validation
- round-trip enforcement
- address mutation and rebuild
- workspace adapters for sandbox and resource editing

UI ownership includes:

- address-tree inspection
- node addition and removal intents
- structure-aware editing surfaces
- presentation of warnings and invalidity reasons

The UI should not author raw SAMRAS magnitudes as the normal editing path. Canonical save writes the structural bitstream only. Legacy hyphenated human-authored magnitudes are migration-only inputs.

## Boundaries

This page owns the responsibility split between engine and UI. It does not own:

- the structural encoding rules themselves
- historical dedicated SAMRAS page milestones
- general `SYSTEM` shell composition
- resource inventory policy

## Authoritative Paths / Files

- `docs/shape_addressed_mixed-radix_address_space.md`
- `docs/SANDBOX_ENGINE.md`
- `portals/_shared/portal/samras/`

## Source Docs

- `docs/shape_addressed_mixed-radix_address_space.md`
- `docs/SANDBOX_ENGINE.md`
- `docs/SAMRAS_PAGE.md`

## Update Triggers

- Changes to engine module ownership
- Changes to UI editing authority
- Changes to canonical write format
- Changes to compatibility treatment of legacy SAMRAS forms
