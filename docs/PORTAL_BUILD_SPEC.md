# Portal Build Spec

## Purpose

Each active portal carries a repo-owned `build.json` used to materialize live file-backed state.

Active specs:

- `portals/mycite-le_example/build.json`
- `portals/mycite-le_fnd/build.json`
- `portals/mycite-le_tff/build.json`

## Authority boundary

`build.json` is authoritative for seeded portal configuration and network/runtime scaffolding, including:

- portal identity metadata
- **tools**: enabled tools and tool mounts
- **private config**: canonical private config payloads
- **hosted**: hosted payloads (`private/network/hosted.json`) and progeny templates
- **profiles/cards**: public profile/card payloads
- **network seeds**: seeded alias/profile/request-log/contract payloads under `private/network/**`

It is not authoritative for live anthology content.

### Hosted vs tools vs profiles

Although they share a common spec file, the responsibilities are separable:

- **Hosted interface** (`hosted` section)
  - defines subject-congregation style, tabs (e.g. `stream`, `discover`, `calendar`, `workflow`), broadcaster pages, and progeny templates
  - materializes to `private/network/hosted.json`
  - edited at runtime via the Hosted/Progeny workbenches
- **Tools** (`tools` section)
  - enables or retires tools and chooses their mount targets (e.g. `peripherals.tools`)
  - does not define hosted pages directly
- **Profiles and cards** (`public_profiles` and related sections)
  - define MSN contact cards and brand profiles
  - may expose public `accessible` metadata used by discovery/hosted pages

In future, a portal may factor `hosted` into a dedicated JSON file consumed by `build.json`, but the authority boundary remains the same: `build.json` (plus any referenced hosted config) is the source of truth for the initial hosted layout; `private/network/hosted.json` is the live, normalized representation used by the runtime.

## Contract seeding

Seeded contract payloads may include canonical MSS context fields:

- `owner_selected_refs`
- `owner_mss`
- `counterparty_mss`

Current build specs seed contract examples for:

- `portal_demo_contract`
- `member_alias_profile`

Those fields are raw bitstrings and selected local datum refs, not base64/hex wrappers.

## Materialized outputs

Materialization writes only the state files the runtime expects, including:

- `private/config.json`
- `private/network/hosted.json`
- `private/network/contracts/*.json`
- public profile cards
- declared seed payloads under `private/network/*`, `private/utilities/vault/*`, and `data/presentation/*`

Materialization does not overwrite `data/anthology.json`.

## Commands

Capture current source/state into build specs:

```bash
python3 portals/scripts/portal_build.py capture
```

Materialize build specs into live state:

```bash
python3 portals/scripts/portal_build.py materialize
```

## Related docs

- `docs/MSS_COMPACT_ARRAY_SPEC.md`
- `docs/NETWORK_PAGE_MODEL.md`
- `docs/CANONICAL_DATA_ENGINE.md`
- `docs/HOSTED_SESSIONS.md`
