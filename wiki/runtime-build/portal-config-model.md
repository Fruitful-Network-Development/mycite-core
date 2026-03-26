# Portal Config Model

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Runtime And Build](README.md)

## Status

Canonical

## Parent Topic

[Runtime And Build](README.md)

## Current Contract

Portal runtime configuration remains instance-led. `private/config.json` is canonical for enabled tools, anchors, and mount targets.

Canonical config sections are:

- instance identity and network keys (`msn_id`, contracts, aliases, hosted)
- `tools_configuration`
- optional portal behavior/profile overlays (compatibility-readable)

Canonical `tools_configuration[]` fields are:

- `name` (tool slug, e.g. `fnd-ebi`, `agro-erp`)
- `anchor` (e.g. `tool.<msn_id>.<tool-slug>.json`)
- `mount_target` (`utilities` or `peripherals.tools`)
- optional title and managing contract metadata

Compatibility reads still accept legacy `tool_id`/`id` fields, but runtime normalizes manifest slugs to provider ids for import (`-` -> `_`).

## Boundaries

This page owns portal config canonicalization. It does not own:

- build-spec seeding rules in depth
- hosted/progeny instance payloads
- contract policy semantics
- shell composition
- provider-specific mediation rendering

## Authoritative Paths / Files

- `compose/portals/state/<instance>/private/config.json`
- `portals/_shared/portal/tools/runtime.py`
- `portals/_shared/portal/runtime_paths.py`

## Source Docs

- `docs/PORTAL_UNIFIED_MODEL.md`

## Update Triggers

- Changes to canonical config sections
- Changes to legacy compatibility reads or reports
- Changes to unified output field names
- Removal planning for legacy config fallbacks
