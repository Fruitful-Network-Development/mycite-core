# AGRO-ERP

Canonical name: `AGRO-ERP`  
Tool family posture: `carry_forward as one agricultural datum family`  
Primary exposure: `internal-admin` first  
Primary read/write posture: `read-only first`

## 1. Completion intent

`AGRO-ERP` should be the single agricultural taxonomy and profile tool family.

Its primary completion center is not generic workflow parity. It is:

- TXA SAMRAS taxonomy
- species profiles
- agricultural datum inspection
- supporting chronology and spatial lenses where useful

It should be similar to the Maps tool in being datum-backed and server-composed, but its core object is taxonomy and species data rather than map projection itself.

## 2. Source basis

Repo sources investigated:

- `docs/plans/v2.3-tool_surface_packet/agro_erp.md`
- `docs/wiki/legacy/tools/agro-erp-mediation.md`
- `docs/wiki/legacy/tools/time-address-schema.md`
- `docs/contracts/admin_maps_read_only_surface.md`
- `docs/wiki/legacy/hops/homogeneous_ordinal_partition_structure.md`

The strongest current V2 packet says AGRO-ERP is a later carry-forward datum-backed tool after Maps. The strongest legacy concept sources say AGRO should remain a mediated provider over authoritative agricultural data, chronology, and spatial context rather than a second shell.

## 3. Core V2.3 position

`AGRO-ERP` should complete as one agricultural datum family with multiple lenses.

Primary lens:

- TXA SAMRAS taxonomy and species profiles

Supporting lenses:

- chronology when agricultural timing matters
- spatial context when land or coordinate context matters

The core tool should not be a map-first tool and should not be a generic agricultural workspace.

## 4. Stable source-of-truth model

The stable authority should be agricultural datum documents and related source-backed records, including taxonomy structures and profile data.

The conceptual authority layers should be:

- TXA SAMRAS taxonomy structures
- species profile documents
- supporting agricultural source records
- derived spatial/chronological projections

Chronology and maps are supporting projections. They do not replace taxonomy truth.

## 5. Family structure

### 5.1 Taxonomy lens
Primary default lens.

Must support:

- browsing TXA SAMRAS structures
- structural inspection of taxonomy nodes
- species profile selection
- profile summaries
- relationship visibility

### 5.2 Species profile lens
A focused view over one species or agricultural profile.

May include:

- descriptors
- classifications
- supporting refs
- status summaries
- related records

### 5.3 Chronology lens
A supporting agricultural timing lens.

When used, it should respect authority-driven time schemas and fail closed rather than invent defaults.

### 5.4 Spatial lens
A supporting agricultural location/region lens.

This may later share projection ideas with Maps, but the agricultural datum remains primary.

## 6. Completion slices

### Slice 1 — read-only taxonomy and species profile inspection
This is the required first completion slice.

It should:

- inspect authoritative agricultural taxonomy structures
- show species profiles
- expose source-backed read models
- remain admin-first and read-only

### Slice 2 — chronology support
Later read-only.

### Slice 3 — spatial support
Later read-only.

### Slice 4 — bounded agricultural edits
Only after authority, preview/apply, audit, and rollback rules are explicit.

## 7. Similarity to Maps

The correct similarity to Maps is structural, not semantic.

Like Maps, AGRO-ERP should be:

- datum-backed
- server-composed
- diagnostic-friendly
- explicit about raw authority vs projections

Unlike Maps, its default object is not coordinate projection. Its default object is taxonomy and species identity.

## 8. Do not carry forward

Do not carry forward:

- a second agricultural shell
- broad workflow parity as the first milestone
- tool-owned shell behavior
- chronology defaults invented from wall-clock assumptions
- treating map views as the core truth
- a generic mixed agricultural workspace that blurs taxonomy, profile, and workflow concerns

## 9. Acceptance boundary

`AGRO-ERP` is complete when:

- one read-only admin slice exists for TXA SAMRAS taxonomy and species profiles
- chronology and spatial views remain supporting lenses, not the primary truth
- the family stays one root tool rather than fragmented into taxonomy/maps/chronology roots
- bounded writes remain deferred until preview/apply and audit rules are explicit

## 10. Recommended V2.3 landing statement

Treat `AGRO-ERP` as one agricultural datum tool with TXA SAMRAS taxonomy and species profiles as the primary view. Use chronology and spatial context as supporting lenses, not as separate root tools and not as the primary authority surface.
