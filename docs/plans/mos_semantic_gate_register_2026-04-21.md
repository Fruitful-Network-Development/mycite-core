# MOS Semantic Gate Register

Date: 2026-04-21

Doc type: `plan`  
Normativity: `supporting`  
Lifecycle: `active`  
Last reviewed: `2026-04-21`

## Purpose

Register the unresolved semantic closure work required by Track B of `docs/plans/master_plan_mos.md` so the SQL cutover can proceed without silently promoting unresolved identity and mutation rules into canon.

## Scope

In scope:

- `SG-1` version identity and MSS hashing policy
- `SG-2` hyphae derivation and stable semantic identity policy
- `SG-3` deterministic edit/remap algorithm for insert/delete/move
- `SG-4` native-standard closure criteria and compatibility retirement rules

Out of scope:

- performing the full semantic closure in this first SQL cutover pass
- promoting any unresolved semantic claim into the v1 operational authority declaration

## Canonical Contract Links

- portal shell contract: `docs/contracts/portal_shell_contract.md`
- route model: `docs/contracts/route_model.md`
- surface catalog: `docs/contracts/surface_catalog.md`
- vocabulary glossary: `docs/contracts/portal_vocabulary_glossary.md`
- CTS-GIS HOPS profile sources: `docs/contracts/cts_gis_hops_profile_sources.md`
- SAMRAS structural model: `docs/contracts/samras_structural_model.md`
- SAMRAS validity and mutation: `docs/contracts/samras_validity_and_mutation.md`

## Gate Backlog

### SG-1 — Version identity and MSS hashing policy

Current state:

- current repo evidence supports canonical MSS compile/decode references
- no current repo-implemented `version_hash` hashing algorithm is closed canon

Required outputs:

- declared hash input and canonicalization boundary
- compatibility rules for historical MSS forms
- authority statement defining when version identity is storage-derived versus semantic-derived

### SG-2 — Hyphae derivation and stable semantic identity policy

Current state:

- the repo distinguishes compact storage address from stable semantic identity
- generalized hyphae derivation is not yet closed canon

Required outputs:

- derivation algorithm
- treatment of preceding rudi datums beyond explicit references
- edge-case matrix for source/file/workbench projections

### SG-3 — Deterministic edit/remap algorithm

Current state:

- bounded structural mutation exists in parts of the repo
- no generalized datum-file insert/delete/move remap algorithm is closed canon

Required outputs:

- ordered transactional remap rules
- preview/apply parity rules
- reference-shift invariants across affected abstractions

### SG-4 — Native-standard closure and compatibility retirement rules

Current state:

- closure criteria remain blocked by `SG-1` through `SG-3`

Required outputs:

- declaration checklist for native MOS closure
- compatibility retirement policy and warning window
- explicit standard-closure language distinct from the v1 operational SQL-backed core declaration

## Validation Rules

1. None of the four gates may be marked closed without a dedicated closure artifact.
2. No Track A milestone may assume a gate is solved unless the closure artifact exists.
3. Compatibility retirement cannot begin before `SG-1` through `SG-3` are closed.

## Exit Criteria

- all four gates have named closure artifacts
- the semantic gap register in `master_plan_mos.md` is empty
- native MOS closure and compatibility retirement are both decision-complete
