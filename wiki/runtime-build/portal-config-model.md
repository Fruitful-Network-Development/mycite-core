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
- reference declarations (`references`; legacy `refferences` is read-only compatibility and normalized at loader boundary)
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
| `data/references/ref.<source_msn_id>.*.json` | inherited resource reference pointers | data engine + inherited resource loaders | inherited linkage | legacy consumer-named filenames | canonicalized to source/provider msn id at config loader boundary |
| `private/utilities/tools/fnd-ebi/fnd-ebi.*.json` | FND-EBI profile contract (`domain`, `site_root`, analytics settings) | service-tool mediation context builder | local-only | legacy schema omission | normalized to `mycite.service_tool.fnd_ebi.profile.v1` |
| `private/utilities/tools/aws-csm/aws-csm.*.json` | AWS-CMS profile contract (identity/smtp/verification/provider staging) | service-tool mediation context builder | local-only | mixed legacy flat fields | normalized to `mycite.service_tool.aws_csm.profile.v1` |
| `private/utilities/tools/aws-csm/aws-csm.collection.json` | optional legacy collection descriptor | service-tool mediation context builder | local-only | treated as canonical by mistake | compatibility-read only; anchor remains canonical |

Boundary statement:

- Tool exposure/enablement: `private/config.json`
- Sandbox anchor identity: `private/config.json` (`tools_configuration[].anchor`) + matching `tool.*` file
- AGRO property/polygon staging: `public/fnd.<msn_id>.json` + referenced anthology/resources
- Chronological schema authority: AGRO tool anchor datum `1-1-1`
- Inherited/local boundary: resource/reference registries and contracts (never inferred from UI mode)
- Reference naming policy: `ref.<source_msn_id>.<name>.json` (source/provider msn id), with legacy consumer-named entries normalized once in `config_loader`

## Normalization Policy Notes

- `references` is canonical; `refferences` is legacy input only and is removed from normalized runtime payloads.
- Tool anchors are canonical for service tool collection identity:
  - `tool.<msn_id>.fnd-ebi.json`
  - `tool.<msn_id>.aws-csm.json`
- Progeny logical ids are canonical dotted tokens:
  - `progeny.<provider_msn_id>.<progeny_type>.<alias_associated_msn_id>`
  - On-disk mapping remains `msn-<provider_msn_id>.<progeny_type>-<alias_associated_msn_id>.json` at a single adapter boundary (`progeny_workspace`).

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
