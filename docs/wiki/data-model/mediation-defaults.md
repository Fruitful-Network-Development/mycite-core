# Mediation Defaults

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Data Model](README.md)

## Status

Canonical

## Parent Topic

[Data Model](README.md)

## Current Contract

Shared mediation defaults convert stored `reference` and `magnitude` pairs into user-facing values and back without portal-instance-specific decode rules.

Each registry entry defines:

- matching logic
- decode
- encode
- magnitude validation
- value validation
- render hint

Current default standard IDs include:

- `boolean_ref`
- `ascii_char`
- `dns_wire_format`
- `text_byte_format`
- `timestamp_unix_s`
- `duration_s`
- `length_m`
- `coordinate`

Unknown standards are non-fatal. They return raw values with warnings rather than breaking the entire decode path.

Coordinate mediation remains important because it now prefers HOPS mixed-radix coordinate addresses while preserving fixed-width hex decoding as a compatibility path for legacy data.

## Boundaries

This page owns the shared mediation registry contract. It does not own:

- datum rule-policy classification
- AGRO-specific orchestration
- MSS compile and decode logic
- shell-level interface panel projections

## Authoritative Paths / Files

- `docs/DATUM_MEDIATION_DEFAULTS.md`
- `instances/_shared/portal/mediation/`

## Source Docs

- `docs/DATUM_MEDIATION_DEFAULTS.md`
- `docs/CANONICAL_DATA_ENGINE.md`
- `docs/AGRO_ERP_TOOL.md`

## Update Triggers

- Changes to the mediation registry interface
- Changes to default standard IDs or compatibility aliases
- Changes to coordinate decode semantics
- Changes to how warnings and validation results are returned
