# AITAS Context Model (Shared Core)

## Purpose

AITAS is the shared-core context foundation for derived data-engine context:

- Attention
- Intention
- Time
- Archetype
- Space

Current implementation scope is intentionally narrow: only **Archetype** is implemented as a real facet.

This layer is derived from anthology/context resolution and is **not** a second semantic source of truth.

## Implemented now

Shared modules:

- `portals/_shared/portal/data_engine/archetypes.py`
- `portals/_shared/portal/data_engine/aitas_context.py`

Implemented anchor definition:

- `ascii_babel_64`

Definition model includes:

- `archetype_key`
- `family`
- `display_name`
- `chain_pattern`
- `constraint_expectation`
- `lens_key`

## Recognition model

Recognition is definition-driven and derived from:

1. resolved local datum row from anthology (via canonical datum ref)
2. inheritance/abstraction chain derived from row references
3. compiled constraint summary derived from row/chain context

For `ascii_babel_64`, matcher requires both:

- chain evidence containing ascii+babel markers
- compiled constraints indicating:
  - `field_length = 64`
  - `alphabet_cardinality = 256`

MSS/closure-related fields are optional supporting evidence in derived binding metadata. They are not sole semantic matchers.

## Derived binding shape

Archetype bindings are derived and rebuildable. They include:

- `archetype_key`
- `local_ref`
- `canonical_ref`
- `source_identifier` (when available)
- `chain_signature`
- `compiled_constraint`
- `lens_key`
- `closure_hash`
- `closure_form`
- `confidence`
- `derived_at_unix_ms`
- `revision`

No authoritative archetype truth is persisted in profile/config.

## Trace output

The archetype trace output is visualization-ready and includes:

- local/canonical datum refs
- recognized archetype key (if any)
- compiled constraint summary
- ordered chain entries
- trace `nodes` and `edges` for later UI rendering
- lens context hints for future lens selection integration

## API surface

Canonical shared routes:

- `GET /portal/api/data/aitas/archetypes`
- `POST /portal/api/data/aitas/archetype/inspect`
- `POST /portal/api/data/aitas/archetype/trace`
- `GET /portal/api/data/aitas/archetype/bindings`

These routes are shared-core owned under `/portal/api/data/*`.
