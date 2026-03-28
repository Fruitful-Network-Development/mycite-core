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
- reference declarations (`references`; legacy `refferences` accepted for compatibility reads)
- optional portal behavior/profile overlays (compatibility-readable)

Canonical `tools_configuration[]` fields are:

- `name` (tool slug, e.g. `fnd-ebi`, `agro-erp`)
- `anchor` (e.g. `tool.<msn_id>.<tool-slug>.json`)
- `mount_target` (`utilities` or `peripherals.tools`)
- optional title and managing contract metadata

Compatibility reads still accept legacy `tool_id`/`id` fields, but runtime normalizes manifest slugs to provider ids for import (`-` -> `_`).

## Authority Chain (Runtime)

The runtime authority chain is intentionally layered and non-interchangeable:

| artifact | authority role | consumed by | local vs inherited | current drift risk | contract posture |
|---|---|---|---|---|---|
| `private/config.json` | portal-instance runtime authority (tool exposure, enabled status, mount target, anchor filename) | config loader + tool runtime + shell mediation bootstrap | local-only | legacy typo (`refferences`) and legacy id keys | normalized on read; canonical keys remain `tools_configuration` + `references` |
| `private/utilities/tools/<tool>/spec.json` | tool capability declaration (inputs/outputs, inherited dependencies) | tool spec loader + tool-specific services | local-only for instance tool package | confusion with anchor ownership | spec does not define active anchor identity |
| `private/utilities/tools/<tool>/tool.<msn_id>.<tool>.json` | tool sandbox anchor payload (schema/data authority for that sandbox) | tool runtime service layer (AGRO time schema, etc.) | local-only | treating anchor rows as hints instead of authority | engine consumes as authoritative when schema is valid; otherwise fail closed |
| `public/fnd.<msn_id>.json` | profile overlays used by mediated views (property refs, titles, display hints) | AGRO profile staging/read models | may be inherited in future, currently local instance publication | conflation with schema authority | profile data is staging input, not chronology schema authority |
| `public/msn.<msn_id>.json` | public identity/profile metadata and API affordances | profile resolver + UI identity surfaces | local publication | confusion with tool exposure authority | identity/profile only; does not enable tools |
| `data/references/ref.<peer_msn_id>.*.json` | inherited resource reference pointers | data engine + inherited resource loaders | inherited linkage | provider-vs-consumer naming mismatches | treated as reference edge, not sandbox identity |

Boundary statement:

- Tool exposure/enablement: `private/config.json`
- Sandbox anchor identity: `private/config.json` (`tools_configuration[].anchor`) + matching `tool.*` file
- AGRO property/polygon staging: `public/fnd.<msn_id>.json` + referenced anthology/resources
- Chronological schema authority: AGRO tool anchor datum `1-1-1`
- Inherited/local boundary: resource/reference registries and contracts (never inferred from UI mode)

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
