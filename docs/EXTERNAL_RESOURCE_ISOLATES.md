# External Resource Isolates

## Purpose

This shared-core subsystem supports public resource acquisition from remote contact cards without requiring full remote anthology import.

It is implemented in `portals/_shared/portal/data_engine/external_resources/` and is reusable by tools, alias/profile inheritance flows, and future desktop/server runtimes.

## Boundary model

- Public resource acquisition is separate from contract context.
- Contracts remain canonical for relationship-scoped MSS context (`owner_selected_refs`, `owner_mss`, `counterparty_mss`).
- Public resources are normalized into isolate bundles for engine-side reasoning.

## Identity model

Three identities are always tracked:

1. **Local anthology ref**: local storage address identity (not portable across portals).
2. **Isolated semantic identity**: canonical, address-independent datum identity used by planners/tools.
3. **Origin/provenance identity**: source portal, resource/export family, wire variant, fetch hash/revision metadata.

Local anthology addresses are never treated as portable cross-portal identity.

## Contact card public resource descriptors

Contact cards may expose `public_resources[]` descriptors:

- `resource_id`
- `kind`
- `export_family`
- `href`
- optional `lens_hint`
- availability metadata

Legacy `accessible` metadata is still parsable and normalized into the same descriptor model.

## Isolate bundles

Fetched public resources are canonicalized into isolate bundles containing:

- source portal identity
- resource identity and export family
- wire variant
- root isolate reference
- closure signature and closure size
- provenance metadata (source, fetch time, hash)
- normalized isolate datum entries

## Sparse local materialization planning

The shared write planner returns structured plans for target intent:

- prerequisite refs required
- refs already local
- refs satisfiable from public isolate bundle
- missing refs that require auto-create (if allowed)
- ordered write actions (`materialize_from_bundle`, `auto_create_prerequisite`, `create_target`)

Tools submit intent; the shared engine produces plan results.

## Canonical API surface

Shared `/portal/api/data/*` endpoints expose this subsystem:

- `GET /portal/api/data/external/resources`
- `POST /portal/api/data/external/fetch`
- `POST /portal/api/data/external/preview_closure`
- `POST /portal/api/data/external/plan_materialization`

No tool-local API should own these core behaviors.
