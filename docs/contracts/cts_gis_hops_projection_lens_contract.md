# CTS-GIS HOPS Projection Lens Contract

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This document defines the CTS-GIS projection and lens boundary used by the
admin read-only slice.

## Hard rules

- SAMRAS governs node/profile traversal and attention state.
- HOPS governs coordinate decoding and derived spatial projection.
- the browser must not decode HOPS or SAMRAS semantics on its own.
- `intention_token` is opaque to the client; the runtime issues valid options.
- raw datum rows remain visible as underlay evidence; they do not stop being the
  underlying truth just because a lens is active.
- the dominant interface panel is the primary CTS-GIS Hanus lens surface.
- the workbench remains mounted as evidence and diagnostic context.

## Runtime stages

CTS-GIS mediation is composed in four stages:

1. authoritative document intake and datum recognition
2. SAMRAS profile extraction plus lineage/child derivation
3. attention/intention render-set selection
4. HOPS-backed GeoJSON projection and lens packaging

The repo preserves this as a split cache and selection pipeline:

- projection cache by selected document plus lens inputs
- mediation cache by attention and intention over the projected document
- row/feature selection as the cheap final pass over the mediated render set

## Projection boundary

- GeoJSON is a derived projection, not datum truth.
- feature properties may carry CTS-GIS mediation context such as
  `samras_node_id`, `profile_label`, and `lineage`.
- `raw_underlay_visible` changes presentation only; it does not change geometry
  authority or projection legality.
- the GeoJSON widget in the dominant interface panel must render the canonical
  `surface_payload.map_projection`; it must not create a second projection path.
- document catalog, projected-feature tables, diagnostic totals, and raw datum
  evidence remain valid secondary workbench surfaces over the same payload.

## Initial intention tokens

- `0`: render the attention profile itself
- `1-0`: render immediate child profiles of the attention node
- `branch:<node_id>`: render one server-issued direct-child branch

Clients must never invent other token shapes.

## Operator interaction boundary

- the interface panel owns attention shell, intention controls, lens toggles,
  GeoJSON rendering, and concise operator focus
- the workbench owns document switching, expanded evidence review, and raw datum
  inspection
- all operator changes continue to round-trip through
  `POST /portal/api/v2/admin/cts-gis/read-only`
