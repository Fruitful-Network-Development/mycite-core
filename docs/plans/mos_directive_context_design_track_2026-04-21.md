# MOS Directive-Context Design Track

Date: 2026-04-21

Doc type: `plan`  
Normativity: `supporting`  
Lifecycle: `active`  
Last reviewed: `2026-04-21`

## Purpose

Begin Track C from `docs/plans/master_plan_mos.md` by defining where NIMM/AITAS and broader directive-context behavior could later widen the engine without blocking the v1 operational SQL-backed core cutover.

## Scope

In scope:

- future insertion points for directive-context behavior
- explicit v1 non-goals
- boundaries between shared shell behavior and tool-local behavior
- dependencies on Track B semantic gates

Out of scope:

- promoting directive-context behavior into shared-engine canon during the v1 SQL cutover
- rewriting the shared shell around NIMM/AITAS
- redefining current tool-local CTS-GIS mediation as shared-engine truth

## Canonical Contract Links

- portal shell contract: `docs/contracts/portal_shell_contract.md`
- route model: `docs/contracts/route_model.md`
- surface catalog: `docs/contracts/surface_catalog.md`
- vocabulary glossary: `docs/contracts/portal_vocabulary_glossary.md`
- CTS-GIS HOPS profile sources: `docs/contracts/cts_gis_hops_profile_sources.md`
- SAMRAS structural model: `docs/contracts/samras_structural_model.md`
- SAMRAS validity and mutation: `docs/contracts/samras_validity_and_mutation.md`

## Initial Insertion Points

1. Shared shell posture
   - possible future insertion only after shared semantic identity and edit/remap rules are closed
   - current shared shell remains file/workbench-oriented
2. Domain services
   - possible future insertion for normalized directive-state interpretation over stable semantic identities
   - depends on `SG-2` and `SG-3`
3. Tool-local mediation
   - remains the active home for NIMM/AITAS-like behavior in the current repo
   - CTS-GIS mediation remains tool-local until a later widening decision is approved

## V1 Non-Goals

- no shared-shell archetype selector
- no SQL cutover dependency on directive-context closure
- no assumption that current tool-local mediation vocabulary is already universal engine canon

## Design Tasks

1. Map which directive values require stable semantic identity rather than compact storage address.
2. Define what must remain tool-local even after a future widening pass.
3. Define the minimum contract changes that would be required before directive-context behavior could become shared-shell-visible.

## Exit Criteria

- insertion points are explicit
- v1 non-goals are explicit
- dependencies on `SG-2` and `SG-3` are explicit
- the Track C design can progress without blocking Track A cutover
