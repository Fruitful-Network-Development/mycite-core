# Progeny Config Model

## Canonical terminology

- Canonical organizational relationship term: `member`
- Legacy accepted aliases: `tenant`, `board_member`

## Baseline legal-entity types

All legal-entity portals should support baseline type expectations for:

- `poc`
- `member`
- `user`

Organization-specific extensions remain local governance decisions.

## Canonical config file usage

- Canonical runtime config path: `private/config.json`
- Legacy fallback path: `private/mycite-config-*.json`
- Contract policy is a core runtime concern and is not sourced from config payload content.
- Core runtime directories remain:
  - `data/`
  - `tools/`
  - `private/contracts/`

## Config intent

`progeny_config` semantics should define:

- supported progeny types
- expected fields per type
- alias-inheritable fields
- portal-local fields
- required vs optional semantics

## Instance intent

Progeny instance JSON should hold resolved instance values while supporting:

- inherited alias-backed fields
- local portal fields
- future shift toward anthology-reference values over literal scalars

Current canonical instance-storage direction:

- `private/network/progeny/`
- `msn-<provider_msn_id>.<progeny_type>-<alias_associated_msn_id>.json`

Default type templates are no longer expected to live as separate per-type config files. They now live in `private/network/hosted.json -> progeny.templates`.

## Compatibility posture

- Existing APIs and files using `tenant`/`board_member` remain accepted.
- Runtime normalizes to canonical `member` where possible.
- New API surfaces use `member` while legacy aliases remain available.
- Legacy typed progeny directories remain readable during migration, but build capture/materialize now favors the single-directory storage contract.

## Property coordinate notation

For temporary geographic abstraction, property coordinates are represented as one fixed-width hex scalar per coordinate.

- Split each hex scalar into two equal halves.
- Upper half is the row-defining coordinate.
- Lower half is the column-defining coordinate.
- Both halves must use the same fixed bit width and base.

Example:

- Under 16-bits-per-axis notation, `0x012C01C2` decodes as:
  - row: `0x012C`
  - column: `0x01C2`

This encoding keeps coordinates compact while preserving deterministic axis extraction by positional split.
