# mycite-le_example

Dedicated example/demo portal state for anthology base-abstraction workshop.

## Current role

- isolated workshop instance for the starter anthology abstraction
- separate from `tff_portal` so example edits do not land in the TFF working portal
- uses the current TFF-style legal-entity runtime flavor for now to preserve the familiar UI/workbench behavior

## Build spec

Repo-owned build source:

- [`build.json`](build.json)

Materialized live state:

- `/srv/compose/portals/state/example_portal/`

Current shared runtime:

- `../runtime/`
- `../_shared/runtime/flavors/tff/`

Workshop anthology in live state:

- `/srv/compose/portals/state/example_portal/data/anthology.json`

The anthology file remains state-owned and is not overwritten by phase-1 materialization.

## Current recourse

For now, the example portal borrows the current TFF MSN/key material so the existing runtime continues to function without inventing a fake network identity.

Before public/demo exposure, assign a dedicated demo MSN/public key/domain and update the build spec accordingly.

## Canonical docs

- [mycite-core root](../../README.md)
- [Portal Build Spec](../../docs/PORTAL_BUILD_SPEC.md)
- [Canonical Data Engine](../../docs/CANONICAL_DATA_ENGINE.md)
