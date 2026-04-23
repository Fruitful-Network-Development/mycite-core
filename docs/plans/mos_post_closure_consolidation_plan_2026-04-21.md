# MOS Post-Closure Consolidation Plan

Date: 2026-04-21

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-22`

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`
- `docs/plans/master_plan_mos.md`

## Purpose

Define the post-closure consolidation work that follows the completed MOS program without reopening the MOS cut-over or creating a competing master-plan document.

## Governing Boundaries

- `docs/plans/master_plan_mos.md` remains completed and authoritative.
- This file is not a new master plan.
- The MOS cut-over remains complete.
- Host-bound private/public assets remain documented exception scope unless a separate dedicated port plan is created.
- `deployed/fnd/data/**` is retained as non-authoritative historical/test support and remains outside MOS datum authority.
- Shared-engine NIMM/AITAS canon is not widened in this pass.
- `SYSTEM` remains the anthology-centered datum-file workbench at `/portal/system`.
- `workbench_ui` remains a separate SQL authority inspector under `SYSTEM`.
- `workbench_ui` remains read-only and additive-only.

## Bucket 1 - Documentation Canonicalization

Goal:

- keep the post-closure doc set legible, canonical, and free of stale master-plan or pending-cut-over language

Required work:

- maintain `docs/audits/reports/mos_personal_notes_to_canon_crosswalk_2026-04-21.md` as the source-to-canon map for the MOS personal notes named in this pass
- maintain `docs/audits/reports/mos_documentation_supersession_audit_2026-04-21.md` as the current classification of canonical cut-over docs versus historical intermediate evidence
- keep `docs/plans/README.md`, `docs/audits/README.md`, and `docs/audits/reports/mos_program_closure_audit_checklist_2026-04-21.md` synchronized with any new MOS follow-on docs added under `docs/plans/` or `docs/audits/reports/`
- correct stale references that point to obsolete personal-note planning names rather than `docs/plans/master_plan_mos.md`
- keep active MOS docs focused on completed closure posture; historical docs may retain intermediate wording only when they are explicitly marked as historical evidence

Exit:

- active docs point to the completed canonical MOS closure record
- historical intermediates are clearly labeled as historical evidence or superseded artifacts
- no active doc reads as if SQL cut-over is still pending

## Bucket 2 - Retained Exception Scope Planning

Goal:

- keep retained exception scope explicit, bounded, and separate from the completed MOS program

Required work:

- maintain a plain inventory of host-bound private/public assets that remain outside SQL datum authority
- keep `deployed/fnd/data/**` explicitly classified as retained historical/test support rather than active MOS authority
- separate retained exception scope into:
  - host-bound private/public assets without dedicated ports
  - derived-materialization surfaces such as `NETWORK`
  - future widening ideas that are not part of completed MOS closure
- if a retained exception surface now warrants action, create one dedicated port plan for that surface rather than widening MOS closure language
- require any future exception-scope plan to name:
  - why the surface was retained
  - what port or contract would be needed
  - what tests would prove migration or continued retention

Exit:

- retained exception scope is described as separate planning work, not unfinished MOS cut-over
- any future port effort starts from its own dedicated plan instead of reopening `master_plan_mos.md`

## Bucket 3 - Datum-File Workbench Hardening

Goal:

- harden the `workbench_ui` SQL authority inspector without turning it into a heavy parallel UI stack

Required work:

- use this file plus the unified YAML control surfaces as the active follow-on tracker for `workbench_ui`:
  - `docs/plans/planning_audit_manifest.yaml`
  - `docs/plans/planning_task_board.yaml`
- keep `SYSTEM` as the canonical anthology workspace and keep `workbench_ui` as the separate shell-attached, script-backed SQL authority inspector under `SYSTEM`
- preserve the current layered datum table posture, datum row structural coordinates, additive overlay rules, and the deliberate CTS-GIS-first `workbench_ui` landing posture
- keep `workbench_ui` scoped to authoritative SQL-backed documents; retained host-bound/private assets and `NETWORK` materializations remain outside that corpus unless separately ported
- retain the now-deployed minimal hardening baseline:
  - keyboard navigation
  - frozen headers and clearer selection state
  - layer/value-group grouping options
  - raw versus interpreted workbench lens toggle
  - semantic identity badges for `version_hash` and `hyphae_hash`
  - source/overlay visibility controls
- keep any remaining `workbench_ui` follow-on scope limited to optional saved query bundles or sort/filter persistence only when it stays simple and script-grounded

Exit:

- `SYSTEM` remains the reducer-owned anthology workspace
- `workbench_ui` remains a separate shell-attached, read-only, additive-only SQL inspection tool
- the shipped hardening baseline remains intact and any further follow-on work does not introduce a parallel frontend framework

## Verification

- targeted `workbench_ui` runtime tests stay green
- contract-doc alignment stays green after any vocabulary or discoverability updates
- MOS doc/reference integrity checks stay green after any new follow-on docs are added
- `/portal/system` reflectivity closure remains evidenced by:
  - `docs/audits/reports/mos_system_surface_visualization_reflectivity_report_2026-04-22.md`
  - `docs/audits/reports/mos_cutover_intent_integrity_report_2026-04-22.md`
  - `docs/audits/reports/mos_premorice_and_modularization_posture_report_2026-04-22.md`

## Result

The post-closure MOS work is now constrained to documentation canonicalization, retained exception scope planning, and `workbench_ui` SQL authority inspector hardening. The named `/portal/system` reflectivity drift is already closed by the 2026-04-22 closure reports, and anything outside these buckets requires its own dedicated plan rather than reopening the completed MOS cut-over.
