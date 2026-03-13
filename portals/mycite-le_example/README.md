# mycite-le_example

Dedicated example/demo portal state for anthology base-abstraction workshop.

## Current role

- isolated workshop instance for the starter anthology abstraction
- separate from `tff_portal` so example edits do not land in the TFF working portal
- uses the current TFF-style legal-entity runtime flavor for now to preserve the familiar UI/workbench behavior
- carries its own placeholder MSN identity: `0-0-0-0-0-0-0-0-0-0`

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

The example portal is isolated from TFF and keeps its workshop anthology in live state only.

Before public/demo exposure, replace the placeholder MSN/key/domain with the real demo identity you want to publish.

## Canonical docs

- [mycite-core root](../../README.md)
- [Portal Build Spec](../../docs/PORTAL_BUILD_SPEC.md)
- [Canonical Data Engine](../../docs/CANONICAL_DATA_ENGINE.md)
