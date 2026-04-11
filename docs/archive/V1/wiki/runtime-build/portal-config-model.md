# Portal Config Model

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Runtime And Build](README.md)

## Status

Canonical

## Parent Topic

[Runtime And Build](README.md)

## Current Contract

Portal runtime configuration remains instance-led. `private/config.json` is canonical for enabled tools, utility collection selectors, and mount targets.

Canonical config sections are:

- instance identity and network keys (`msn_id`, contracts, aliases, hosted)
- `tools_configuration`
- reference declarations (`references`; legacy `refferences` is read-only compatibility and normalized at loader boundary)
- optional portal behavior/profile overlays (compatibility-readable)

Canonical `tools_configuration[]` fields are:

- `name` (tool slug, e.g. `fnd-ebi`, `agro-erp`)
- `anchor` (e.g. `tool.<msn_id>.<tool-slug>.json`; selects the utility collection/config file only)
- `mount_target` (`utilities` or `peripherals.tools`)
- optional title and managing contract metadata

Compatibility reads still accept legacy `tool_id`/`id` fields, but runtime normalizes manifest slugs to provider ids for import (`-` -> `_`).

## Authority Chain (Runtime)

The runtime authority chain is intentionally layered and non-interchangeable:

| artifact | authority role | consumed by | local vs inherited | current drift risk | contract posture |
|---|---|---|---|---|---|
| `private/config.json` | portal-instance runtime authority (tool exposure, enabled status, mount target, utility collection selector filename) | config loader + tool runtime + shell mediation bootstrap | local-only | legacy typo (`refferences`) and legacy id keys | normalized on read; canonical keys remain `tools_configuration` + `references` |
| `private/utilities/tools/<tool>/spec.json` | tool capability declaration (inputs/outputs, inherited dependencies) | tool spec loader + tool-specific services | local-only for instance tool package | confusion with anchor ownership | spec does not define active anchor identity |
| `private/utilities/tools/<tool>/tool.<msn_id>.<tool>.json` | utility collection/config selector for service-tool files | service-tool mediation context builder | local-only | mistaken as sandbox datum authority | non-datum collection manifest only; may be plain `tool_collection.v1` JSON |
| `data/sandbox/<tool>/tool.<msn_id>.<tool>.json` | tool sandbox datum anchor payload | tool runtime service layer (AGRO time schema, sandbox-local datum authority) | local-only sandbox truth | accidental replacement with utility collection files | authoritative sandbox datum source; fail closed when invalid or missing |
| `public/fnd.<msn_id>.json` | profile overlays used by mediated views (property refs, titles, display hints) | AGRO profile staging/read models | may be inherited in future, currently local instance publication | conflation with schema authority | profile data is staging input, not chronology schema authority |
| `public/msn.<msn_id>.json` | public identity/profile metadata and API affordances | profile resolver + UI identity surfaces | local publication | confusion with tool exposure authority | identity/profile only; does not enable tools |
| `data/references/<source_msn_id>/rf.<source_msn_id>.*.json` | inherited resource/reference materialization | data engine + inherited resource loaders | inherited linkage | legacy root files and legacy `ref.*.json` forms | canonical form is `rf.<source_msn_id>.<name>.bin` with scoped JSON/cache compatibility materialization |
| `data/payloads/*.bin` + `data/payloads/cache/*.json` | compiled payload binaries plus decoded cache materializations | resource registry + contact-card/public payload flows + sandbox import/export | derived from canonical resource/reference state | accidental manual edits | derived artifacts only; rewrite is allowed only during payload/cache materialization |
| `private/utilities/tools/fnd-ebi/fnd-ebi.*.json` | FND-EBI profile contract (`domain`, `site_root`, analytics settings) | service-tool mediation context builder | local-only | legacy schema omission | normalized to `mycite.service_tool.fnd_ebi.profile.v1` |
| `private/utilities/tools/aws-csm/aws-csm.*.json` | AWS-CMS profile contract (identity/smtp/verification/provider staging, placeholder-secret metadata, handoff-boundary state) | service-tool mediation context builder | local-only | mixed legacy flat fields | normalized to `mycite.service_tool.aws_csm.profile.v1` |
| `private/utilities/tools/newsletter-admin/newsletter-admin.<domain>.json` | canonical newsletter operational profile (`list_address`, selected verified sender, queue/Lambda config, inbound-processing state) | AWS-CMS newsletter mediation + AWS newsletter admin routes | local-only | drift against progeny newsletter metadata | canonical operational source; progeny newsletter fields are compatibility-read only |
| `private/utilities/tools/newsletter-admin/runtime_secrets.json` | visible runtime helper secrets for unsubscribe signing and dispatch callbacks | AWS newsletter runtime helpers | local-only | hidden dotfile carryover | canonical helper state; hidden dotfiles are retired |
| `private/utilities/tools/aws-csm/*audit*.json` | non-destructive AWS-CMS audit artifacts (for example FND sender classification reports and SMTP secret health snapshots) | service-tool file collection + operator inspection scripts | local-only | confusion with live profile authority | audit-only; never treated as canonical profile state |

Boundary statement:

- Tool exposure/enablement: `private/config.json`
- Utility collection selector: `private/config.json` (`tools_configuration[].anchor`) + matching `private/utilities/tools/<tool>/tool.*` file
- Sandbox anchor identity: `data/sandbox/<tool>/tool.*`
- AGRO property/polygon staging: `public/fnd.<msn_id>.json` + referenced anthology/resources
- Chronological schema authority: AGRO tool anchor datum `1-1-1`
- Inherited/local boundary: resource/reference registries and contracts (never inferred from UI mode)
- Reference naming policy: canonical `rf.<source_msn_id>.<name>.bin`, with legacy `ref.*.json` / `refferences` accepted only at compatibility boundaries and normalized once in `config_loader`

## Normalization Policy Notes

- `references` is canonical; `refferences` is legacy input only and is removed from normalized runtime payloads.
- Utility collection selectors are canonical for service tool collection identity:
  - `tool.<msn_id>.fnd-ebi.json`
  - `tool.<msn_id>.aws-csm.json`
- Tool sandbox datum anchors live under `data/sandbox/<tool>/tool.<msn_id>.<tool>.json`.
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

- `/srv/mycite-state/instances/<instance>/private/config.json`
- `instances/_shared/portal/tools/runtime.py`
- `mycite_core/runtime_host/paths.py`

## Source Docs

- `docs/plans/tool_dev.md`

## Update Triggers

- Changes to canonical config sections
- Changes to legacy compatibility reads or reports
- Changes to unified output field names
- Removal planning for legacy config fallbacks
