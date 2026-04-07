# Datum Rule Policy

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Data Model](README.md)

## Status

Canonical

## Parent Topic

[Data Model](README.md)

## Current Contract

Datum rule policy classifies rows and controls write and publish behavior.

The frozen stance is:

- `invalid` is blocked by default and requires explicit override for write or promotion
- `ambiguous` is writable for normal users with warnings
- `unknown` is writable for normal users with warnings
- staging and sandbox still compute understanding and policy, but only `invalid` blocks promotion to canonical stores unless override is used

Current status mapping is:

- `standard`: writable and publishable
- `transitional`: writable but not publishable
- `ambiguous`: writable with degraded guidance and warning-heavy UX
- `unknown`: writable with manual-first UX
- `invalid`: blocked unless override

Reference picking follows the same posture:

- default filtered picker when rule information is sufficient
- guided filtered plus manual fallback for ambiguous rows
- manual-first behavior for unknown rows

## Boundaries

This page owns policy classification and write consequences. It does not own:

- core datum identity rules
- shell layout
- MSS contract semantics
- sandbox lifecycle orchestration beyond policy gating

## Authoritative Paths / Files

- `docs/datum_rule_policy_v2.md`
- `instances/_shared/portal/data_engine/rules/policy.py`
- `instances/_shared/portal/data_engine/rules/write_evaluation.py`

## Source Docs

- `docs/datum_rule_policy_v2.md`

## Update Triggers

- Changes to status meanings
- Changes to publish blocking behavior
- Changes to override requirements
- Changes to reference-picker fallback rules
