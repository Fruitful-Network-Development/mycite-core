# CTS-GIS Cross-Domain Module

Composes the authoritative datum-recognition projection into a bounded
CTS-GIS surface for the V2 admin portal.

This module does not own datum authority. It reuses the authoritative datum
document seam plus datum recognition and adds only:

- SAMRAS attention/intention mediation over profile rows
- intra-document linkage from profile rows to geometry rows
- HOPS-backed geographic projection
- title and SAMRAS display overlays
- CTS-GIS-specific selection and lens state
- staged YAML/JSON insert validation, preview, and SQL-backed apply flows

Mutation-capable follow-on work is tracked in
`docs/plans/portal_nimm_aitas_unification_plan_2026-04-24.md`. CTS-GIS accepts
the shared NIMM/AITAS mutation lifecycle names (`stage`, `validate`, `preview`,
`apply`, `discard`) and maps historical action names (`stage_insert_yaml`,
`validate_stage`, `preview_apply`, `apply_stage`, `discard_stage`) as
compatibility adapters only.

Operator edits are normalized through `SamrasTitleLens`, compiled by
`StagingArea` into NIMM manipulation envelopes, previewed in the Workbench, and
applied only by the runtime-owned SQL-backed apply path.
