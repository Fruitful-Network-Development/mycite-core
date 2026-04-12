# Maps

Canonical name: `Maps`  
Legacy crosswalk: `CTS` and similar older map-facing naming should be retired into this name  
Tool family posture: `current V2 family, but vision-led completion expands it into the default app in every portal`  
Primary exposure: `default app in every portal` as the completion target  
Primary read/write posture: `read-only first`

## 1. Completion intent

`Maps` should be the default spatial app in every portal.

The current repo already has a real V2 Maps tool, but its present posture is narrower than the intended end state. The completion document therefore uses the current V2.3 rules and current Maps implementation as the structural starting point, while making the vision target the dominant guide.

## 2. Source basis

Repo sources investigated:

- `docs/plans/v2.3-tool_surface_packet/maps.md`
- `docs/contracts/admin_maps_read_only_surface.md`
- `docs/contracts/tool_exposure_and_admin_activity_bar_contract.md`
- `docs/wiki/legacy/hops/homogeneous_ordinal_partition_structure.md`

These show that Maps is already a current V2 admin read-only tool with shell-owned legality, a runtime entrypoint, authoritative datum reads, diagnostic posture, and HOPS-coordinate decoding.

## 3. Core V2.3 position

`Maps` should remain one tool family.

It should not fragment into:

- admin maps
- public maps
- CTS
- coordinate inspector
- overlay browser

Those should be slices or audiences of the same family.

## 4. Stable source-of-truth model

The current repo evidence is strong on this point:

- authoritative maps documents remain the source of truth
- raw datum rows remain visible
- overlays and projections are derived presentation
- the browser must not decode core spatial structures by itself
- unresolved or invalid map values stay attached to diagnostics rather than being silently plotted

This truth model should remain unchanged as the tool expands to more audiences.

## 5. Completion target

The completion target is a single `Maps` family that becomes the default spatial app everywhere, with audience-specific slices.

### 5.1 Internal-admin slice
Current read-only admin inspection and diagnostics.

### 5.2 Trusted-tenant slice
Later bounded read exposure over the same authority model.

### 5.3 Portal-default slice
A default app posture in every portal that can render approved map-facing views without weakening datum authority or diagnostics.

## 6. Family behavior

`Maps` should own:

- spatial document inspection
- server-composed map payloads
- HOPS-coordinate projection
- overlays and diagnostics
- map-facing default app rendering for approved audiences

It should not own:

- a second datum truth source
- browser-side decoding of HOPS or SAMRAS
- silent projection of invalid values
- generic portal shell ownership

## 7. Legacy crosswalk

Any prior `CTS` naming or similar map-like naming should resolve into `Maps`.

That means:

- one tool id family
- one canonical name
- one descriptor family
- crosswalk older names into `Maps` rather than preserving multiple root names

## 8. Completion slices

### Slice 1 — admin read-only
Already the current V2 reference.

### Slice 2 — default portal read-only map app
This is the first vision-led expansion slice.

It should:

- preserve server-composed projection
- preserve diagnostics
- remain datum-authority-first
- adapt to default-app posture

### Slice 3 — trusted-tenant or broader portal audience
Later.

### Slice 4 — bounded overlays or actions
Only later and only if explicit write semantics exist.

## 9. Do not carry forward

Do not carry forward:

- multiple root names for the same spatial family
- browser-owned projection logic
- silent handling of invalid coordinates
- a second generic data-inspection tool for map data
- tool-owned shell behavior

## 10. Acceptance boundary

`Maps` is complete when:

- `Maps` is the only canonical spatial family name
- it remains datum-authority-first
- it can act as the default spatial app in every portal
- the same truth model works across admin and default-app audiences

## 11. Recommended V2.3 landing statement

Keep `Maps` as one spatial family, retire `CTS`-style naming into it, and expand the existing datum-backed Maps surface until it can serve as the default spatial app in every portal without weakening the current authority and diagnostic posture.
