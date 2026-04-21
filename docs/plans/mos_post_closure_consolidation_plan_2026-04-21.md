# MOS Post-Closure Consolidation Plan

Date: 2026-04-21

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-21`

## Purpose

Define the post-closure consolidation work that follows the completed MOS program without reopening the MOS cut-over or creating a competing master-plan document.

## Governing Boundaries

- `docs/plans/master_plan_mos.md` remains completed and authoritative.
- This file is not a new master plan.
- The MOS cut-over remains complete.
- Host-bound private/public assets remain documented exception scope unless a separate dedicated port plan is created.
- Shared-engine NIMM/AITAS canon is not widened in this pass.
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

- harden the canonical datum-file workbench surface without turning it into a heavy parallel UI stack

Required work:

- use `docs/plans/workbench_ui_hardening_follow_on_2026-04-21.md` as the active follow-on plan for the datum-file workbench
- treat `workbench_ui` as the canonical shell-attached, script-backed datum-file workbench surface
- preserve the current anchor file posture, layered datum table posture, datum row structural coordinates, and additive overlay rules
- keep hardening minimal and utilitarian:
  - keyboard navigation
  - frozen headers and clearer selection state
  - layer/value-group grouping options
  - raw versus interpreted workbench lens toggle
  - semantic identity badges for `version_hash` and `hyphae_hash`
  - source/overlay visibility controls
  - saved filters/sorts only when they stay simple and script-grounded

Exit:

- the datum-file workbench remains shell-attached, read-only, and additive-only
- the follow-on hardening improves navigation and inspection clarity without introducing a parallel frontend framework

## Verification

- targeted `workbench_ui` runtime tests stay green
- contract-doc alignment stays green after any vocabulary or discoverability updates
- MOS doc/reference integrity checks stay green after any new follow-on docs are added

## Result

The post-closure MOS work is now constrained to documentation canonicalization, retained exception scope planning, and datum-file workbench hardening. Anything outside those buckets requires its own dedicated plan and must not reopen the completed MOS cut-over.
