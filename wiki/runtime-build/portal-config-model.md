# Portal Config Model

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Runtime And Build](README.md)

## Status

Canonical

## Parent Topic

[Runtime And Build](README.md)

## Current Contract

Portal runtime configuration is normalized around unified keys rather than older legal-entity split semantics.

Canonical config sections are:

- `portal_profile`
- `portal_behavior`
- `portal_features`

Writes should normalize legacy input into unified fields such as:

- `portal_profile.profile_kind`
- `portal_profile.organization_config_file`
- `portal_behavior.defaults`
- `portal_behavior.overrides`
- `portal_features.workflow_enabled`

Legacy keys remain compatibility-readable for now, and write responses may report when legacy keys were used.

## Boundaries

This page owns portal config canonicalization. It does not own:

- build-spec seeding rules in depth
- hosted/progeny instance payloads
- contract policy semantics
- shell composition

## Authoritative Paths / Files

- `docs/PORTAL_UNIFIED_MODEL.md`
- `portals/_shared/portal/services/portal_model.py`

## Source Docs

- `docs/PORTAL_UNIFIED_MODEL.md`

## Update Triggers

- Changes to canonical config sections
- Changes to legacy compatibility reads or reports
- Changes to unified output field names
- Removal planning for legacy config fallbacks
