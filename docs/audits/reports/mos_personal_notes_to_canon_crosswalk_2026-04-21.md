# MOS Personal Notes To Canon Crosswalk

Date: 2026-04-21

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `completed`
Last reviewed: `2026-04-21`

## Purpose

Map the named MOS personal notes to their current repo status after program closure, identify which concepts are now canonical versus deferred or source-only, and point future readers to the canonical repo files that carry the active meaning.

## Status Legend

- `canonized`: the note's active meaning is now carried by canonical repo docs and implementation without needing the personal note.
- `partially canonized`: some durable concepts are canonical now, but substantial exploratory or over-specific material remains deferred or source-only.
- `deferred`: the note's main idea remains intentionally outside the completed MOS closure scope.
- `superseded`: the note's active meaning has been replaced by canonical docs, closure audits, or explicitly historical evidence.

## Final Disposition Legend

- `retained in place`: the note remains under `docs/personal_notes/MOS/` because it still provides useful source evidence for current repo work.
- `archived`: the note moved to `docs/personal_notes/archive/MOS/` because it is superseded or source-only historical evidence.

## Stale Reference Cleanup

- The stale personal-note master-plan basename was removed from `docs/personal_notes/archive/MOS/cuttover_consideration.md`.
- The canonical MOS program file is `docs/plans/master_plan_mos.md`.
- The personal-note master-plan precursor under `docs/personal_notes/archive/MOS/` remains historical source material only and is not a canonical planning file.

## Summary

| Personal note | Status | Final disposition | Active meaning now lives in |
|---|---|---|---|
| `docs/personal_notes/MOS/data_base_use_findings.md` | `partially canonized` | `retained in place` | MOS closure plan/policies plus shell/workbench contracts |
| `docs/personal_notes/archive/MOS/datum_logic_area_investigation_clarity.md` | `superseded` | `archived` | `SG-1` through `SG-3`, Track C design, and closure audits |
| `docs/personal_notes/MOS/mos_novelty_definition.md` | `partially canonized` | `retained in place` | `docs/plans/mos_novelty_positioning_follow_on_2026-04-21.md` plus MOS identity policies |
| `docs/personal_notes/MOS/mos_sql_backed_core_declaration_draft.md` | `canonized` | `retained in place` | MOS master plan and final closure audits |
| `docs/personal_notes/MOS/mycelial_ontological_schema.md` | `partially canonized` | `retained in place` | MOS identity/remap policies plus datum-file workbench contracts |
| `docs/personal_notes/archive/MOS/cuttover_consideration.md` | `superseded` | `archived` | closure audits, follow-on plans, and post-closure supersession audit |
| `docs/personal_notes/archive/MOS/mos_master_plan.md` | `superseded` | `archived` | `docs/plans/master_plan_mos.md` as the only canonical MOS program document |

## Note Crosswalk

### `docs/personal_notes/MOS/data_base_use_findings.md`

Status: `partially canonized`

Final disposition: `retained in place`

Canonical now:

- file-shaped outward authority remains canonical for the MOS datum environment
- ordered `layer-value_group-iteration` datum rows are canonical storage coordinates
- document-level `version_hash` and row-level `hyphae_hash` are canonical SQL identities
- additive directive overlays remain separate from authoritative datum rows

Deferred:

- shared-engine NIMM/AITAS widening beyond additive overlays
- any dedicated port plan for host-bound private/public assets outside the completed MOS scope

Source-only:

- the note's proposed normalized table set for `sandboxes`, `geometry_rings`, `collections`, `yaml_configs`, and other speculative schema tables
- hover-watermark lens behavior as a concrete UI contract
- YAML task configuration as a MOS data-model requirement

Canonical repo files:

- `docs/plans/master_plan_mos.md`
- `docs/plans/mos_sg1_version_identity_policy_2026-04-21.md`
- `docs/plans/mos_sg2_hyphae_derivation_policy_2026-04-21.md`
- `docs/plans/mos_sg3_edit_remap_policy_2026-04-21.md`
- `docs/plans/mos_directive_context_design_track_2026-04-21.md`
- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/surface_catalog.md`

### `docs/personal_notes/archive/MOS/datum_logic_area_investigation_clarity.md`

Status: `superseded`

Final disposition: `archived` from `docs/personal_notes/MOS/datum_logic_area_investigation_clarity.md`

Canonical now:

- the repo has an explicit `version_hash` policy and storage boundary
- the repo has an explicit `hyphae_hash` derivation policy and semantic-identity boundary
- the repo has an explicit deterministic insert/delete/move remap policy
- directive context is explicitly additive-only and non-blocking

Deferred:

- future shared-engine NIMM/AITAS canon beyond the additive Track C seam

Source-only:

- the note's commit-history archaeology as the place to resolve current repo truth
- its open-question posture; those questions are no longer the active canonical state

Canonical repo files:

- `docs/plans/master_plan_mos.md`
- `docs/plans/mos_semantic_gate_register_2026-04-21.md`
- `docs/plans/mos_sg1_version_identity_policy_2026-04-21.md`
- `docs/plans/mos_sg2_hyphae_derivation_policy_2026-04-21.md`
- `docs/plans/mos_sg3_edit_remap_policy_2026-04-21.md`
- `docs/plans/mos_directive_context_design_track_2026-04-21.md`

### `docs/personal_notes/MOS/mos_novelty_definition.md`

Status: `partially canonized`

Final disposition: `retained in place`

Canonical now:

- MOS is positioned internally as datum-native rather than record-first, document-first, or graph-first
- the strongest durable distinction is the combination of storage-derived document identity and semantic-derived row identity
- prior-art boundaries are explicit: MOS should not overclaim novelty for graphs, linked data, canonicalization, content addressing, or append-only logs in isolation

Deferred:

- any public legal, patent, or broad external novelty claim beyond the internal positioning/spec note
- any novelty claim that depends on future shared-engine NIMM/AITAS widening

Source-only:

- the note's stronger website-driven rhetoric that exceeds current repo proof
- claims that depend on unproven or unpublished mechanisms rather than current canonical policies

Canonical repo files:

- `docs/plans/mos_novelty_positioning_follow_on_2026-04-21.md`
- `docs/plans/mos_sg1_version_identity_policy_2026-04-21.md`
- `docs/plans/mos_sg2_hyphae_derivation_policy_2026-04-21.md`
- `docs/plans/master_plan_mos.md`

### `docs/personal_notes/MOS/mos_sql_backed_core_declaration_draft.md`

Status: `canonized`

Final disposition: `retained in place`

Canonical now:

- the MOS cut-over is a completed SQL-backed core program for the approved repo scope
- file-shaped outward contracts remain canonical even though authority is SQL-backed
- portal grants, tool exposure, datum authority, and audit storage are in the SQL-owned surface set
- host-bound private/public assets remain documented exception scope rather than unfinished cut-over work

Deferred:

- any separate dedicated port program for host-bound exception surfaces

Source-only:

- draft-era exploratory framing now replaced by the completed authoritative closure record

Canonical repo files:

- `docs/plans/master_plan_mos.md`
- `docs/audits/reports/mos_fnd_sql_ingestion_coverage_report_2026-04-21.md`
- `docs/audits/reports/mos_sql_only_authority_activation_and_legacy_retirement_2026-04-21.md`
- `docs/audits/reports/mos_program_closure_report_2026-04-21.md`
- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`

### `docs/personal_notes/MOS/mycelial_ontological_schema.md`

Status: `partially canonized`

Final disposition: `retained in place`

Canonical now:

- the anchor file and datum row remain first-class repo concepts
- structural coordinates remain `layer`, `value_group`, and `iteration`
- the datum-file workbench remains a layered datum table over the canonical system anchor file
- row semantic identity and deterministic remap rules are now canonical and explicit

Deferred:

- future shared-engine directive/NIMM/AITAS schema widening
- any broader generalized relational decomposition beyond the current SQL authority implementation

Source-only:

- the note's speculative normalized table layout for SAMRAS/HOPS internals, lens tables, and ancillary configuration tables
- any schema element not adopted by the current SQL adapters, closure policies, or contracts

Canonical repo files:

- `docs/plans/master_plan_mos.md`
- `docs/plans/mos_sg1_version_identity_policy_2026-04-21.md`
- `docs/plans/mos_sg2_hyphae_derivation_policy_2026-04-21.md`
- `docs/plans/mos_sg3_edit_remap_policy_2026-04-21.md`
- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`

### `docs/personal_notes/archive/MOS/cuttover_consideration.md`

Status: `superseded`

Final disposition: `archived` from `docs/personal_notes/MOS/cuttover_consideration.md`

Canonical now:

- the MOS cut-over remains complete and must not be reopened
- host-bound private/public assets remain retained exception scope unless a separate dedicated port plan is created
- `workbench_ui` is the follow-on SQL authority inspector surface for read-only, additive-only hardening under `SYSTEM`
- historical intermediate MOS docs are retained as historical evidence rather than active authority

Deferred:

- retained exception scope planning as a separate post-closure concern
- `workbench_ui` hardening beyond the current read-only two-pane SQL inspection baseline

Source-only:

- the note's prompt log, execution transcript, and open-ended cut-over staging language
- any wording that frames exception scope as unfinished MOS closure work

Canonical repo files:

- `docs/plans/master_plan_mos.md`
- `docs/plans/mos_post_closure_consolidation_plan_2026-04-21.md`
- `docs/plans/workbench_ui_hardening_follow_on_2026-04-21.md`
- `docs/audits/reports/mos_program_closure_report_2026-04-21.md`
- `docs/audits/reports/mos_documentation_supersession_audit_2026-04-21.md`
- `docs/audits/reports/workbench_ui_utilitarian_design_audit_2026-04-21.md`

### `docs/personal_notes/archive/MOS/mos_master_plan.md`

Status: `superseded`

Final disposition: `archived` from `docs/personal_notes/MOS/mos_master_plan.md`

Canonical now:

- `docs/plans/master_plan_mos.md` is the only canonical MOS program document
- the YAML companion index is a supporting index only and not a competing planning file

Source-only:

- the archived precursor remains useful only as prompt/transcript evidence for how the canonical plan was shaped
- it must not be treated as active planning authority

Canonical repo files:

- `docs/plans/master_plan_mos.md`
- `docs/plans/master_plan_mos.index.yaml`
- `docs/audits/reports/mos_documentation_supersession_audit_2026-04-21.md`

## Result

The named MOS personal notes are now fully cross-walked into the post-closure repo state. The active MOS authority remains `docs/plans/master_plan_mos.md`; `data_base_use_findings.md`, `mos_sql_backed_core_declaration_draft.md`, `mycelial_ontological_schema.md`, and `mos_novelty_definition.md` remain in place as source evidence; and `cuttover_consideration.md`, `datum_logic_area_investigation_clarity.md`, and `mos_master_plan.md` are archived as historical/source-only evidence rather than active authority.
