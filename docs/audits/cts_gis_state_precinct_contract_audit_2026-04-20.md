# CTS-GIS State Precinct Contract Audit (Ohio)

## Scope

- Source profile under audit:
  - `deployed/fnd/data/sandbox/cts-gis/sources/sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17.json`
- Runtime/UI contract areas:
  - state time defaults
  - precinct overlay gating
  - Diktataograph/Garland layout containment
- Terminology hardening:
  - filament datum
  - hyphae value

## Findings

### 1) Source legality drift in Ohio state source

Automated row audit over `datum_addressing_abstraction_space` found:

- total rows: `58`
- `4-*` rows: `29`
- `4-*` rows violating coordinate-ring contract (`rf.3-1-1` alternating requirement): `2`
  - `4-2-1` uses `rf.3-1-6`
  - `4-84-1` uses repeated `rf.3-1-4`

These are not legal spatial-HOPS coordinate ring rows under the CTS-GIS profile-source contract and should not be used as geometry rows in the `4 -> 5 -> 6 -> 7` projection chain.

### 2) Filament datum still present as forward binding

Owner row is still present:

- `7-4-1` binds:
  - primary node: `3-2-3-17`
  - secondary related node: `3-2-3-25-1-1-1-1`
  - primary collection: `6-0-1`
  - additive collection: `6-0-2`

This confirms the intended forward-facing access point still exists, but additive collection legality/time applicability must be validated by contract-aware logic.

### 3) Time applicability labels exist but were not canonicalized

State source labels include:

- `aplicable_time_frame`
- `precinct_group-1`
- `23_present-district_31`

These show intended timeframe semantics but include spelling/normalization drift and were not consistently driving runtime default behavior.

### 4) Validation coverage gap allowed illegal state rows

Repair validator behavior for state-like nodes was permissive in previous passes; strict contract checks were only applied to Summit lineage assumptions. This allowed non-legal state row families to remain while rendering still appeared partially functional.

### 5) UI containment issue confirmed

The Diktataograph section could still visually over-expand for long row sets, causing the Garland area to appear similarly expanded. Containment needed stricter bounded-height + overflow behavior on stage containers, not only top-level split ratios.

## Contract Intent (for remediation)

- Spatial geometry projection contract remains strict:
  - `4-*`: coordinate tokens (`rf.3-1-1` + HOPS coordinate tokens)
  - `5-*`: polygon members pointing to `4-*`
  - `6-*`: collection wrappers pointing to `5-*`
  - `7-*`: owner bindings pointing to one primary `6-*` plus optional additive `6-*` links
- Additive precinct/district sets are allowed only when:
  - bound through legal owner-collection references
  - gated by explicit time applicability in runtime mediation

## Remediation Direction

- Keep the filament datum as the forward-facing source entrypoint.
- Preserve additive district/precinct collection references.
- Move non-spatial adjunct payload out of illegal `4-*` coordinate encoding assumptions.
- Enforce strict legality checks for state profiles and fail loudly on illegal row-family use.

