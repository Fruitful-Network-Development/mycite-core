# Plans

This directory now runs as part of one unified planning/audit system.

Active shell refactor records preserve the family-only shell closeout posture.

## Start Here

- Operating guide: `docs/plans/planning_audit_operating_system.md`
- Context manifest (canonical cross-directory map): `docs/plans/contextual_system_manifest.yaml`
- Context task board (organization and closure work): `docs/plans/contextual_system_task_board.yaml`
- Compatibility initiative/task surfaces:
  - `docs/plans/planning_audit_manifest.yaml`
  - `docs/plans/planning_task_board.yaml`

## Canonical Plan Set

- `documentation_ia_remediation_backlog.md`
- `documentation_responsibility_alignment_backlog_2026-05-01.md`
- `desktop_dm02_dm04_reconciliation_plan_2026-04-20.md` (active)
- `aws_csm_operational_recovery_plan_2026-04-24.md` (active)
- `portal_nimm_aitas_unification_plan_2026-04-24.md` (completed)
- `mos_post_closure_consolidation_plan_2026-04-21.md` (completed)
- `portal_legacy_boundary_sql_mos_convergence_plan_2026-04-23.md` (completed)
- `code_bloat_deep_audit_program_plan_2026-04-24.md` (completed planning foundation)
- `code_bloat_remediation_execution_plan_2026-04-25.md` (active)
- `one_shell_portal_refactor.md`
- `one_shell_stabilization_matrix.md`
- `mos_novelty_positioning_follow_on_2026-04-21.md` (positioning/spec context only)
- `refinement.md` (completed foundation for NIMM/AITAS/lens/staging)

`portal_nimm_aitas_unification_plan_2026-04-24.md` is the canonical completed
plan for cross-tool NIMM/AITAS/lens/stage unification across CTS-GIS and
AWS-CSM. The completed refinement stream remains foundation history, not a
second plan for this follow-on work.

`aws_csm_operational_recovery_plan_2026-04-24.md` is the canonical active
recovery plan for deployed-FND AWS-CSM operability (per-domain onboarding,
personal-email confirmation forwarding, onboard-state visibility, performance,
and residual JSON-path retirement).

`code_bloat_deep_audit_program_plan_2026-04-24.md` is the completed planning
foundation that produced seven deep audit tracks from
`docs/audits/reports/code_bloat_diagnosis.md`.

`code_bloat_remediation_execution_plan_2026-04-25.md` is the canonical active
corrective execution plan for implementing the diagnosis-derived fixes with
stable remediation task IDs.

`documentation_responsibility_alignment_backlog_2026-05-01.md` is the canonical
lossless follow-on backlog for:

- documentation family alignment
- personal-note promotion/extraction
- FND-EBI peripheral split
- host capability bootstrap clarification

Deferred agentic task anchors for that stream:

- `FND-EBI-Peripheral-Split-2026-05-01`
- `Portal-Host-Capability-Bootstrap-2026-05-01`

## Completed And Historical Support Set

- Shell-unification closeout set is `Lifecycle: completed`:
  - `portal_shell_boundary_map_and_system_workbench_split_2026-04-23.md`
  - `portal_shell_runtime_bundle_unification_2026-04-23.md`
  - `portal_shell_region_family_renderer_migration_2026-04-23.md`
  - `portal_shell_unification_execution_plan_2026-04-23.md`
  - `portal_shell_unification_plan_index_2026-04-23.md`
- MOS closure support artifacts are retained as `historical-superseded`:
  - `mos_semantic_gate_register_2026-04-21.md`
  - `mos_sg1_version_identity_policy_2026-04-21.md`
  - `mos_sg2_hyphae_derivation_policy_2026-04-21.md`
  - `mos_sg3_edit_remap_policy_2026-04-21.md`
  - `mos_sg4_standard_closure_policy_2026-04-21.md`
  - `mos_directive_context_design_track_2026-04-21.md`
- `archive/` retains superseded historical plan artifacts.
- Legacy index artifact `master_plan_mos.index.yaml` is retained as
  `historical-superseded` with canonical replacement pointer to
  `contextual_system_manifest.yaml` + `contextual_system_task_board.yaml`.

## Contextual System Rule

- Every active stream should have one canonical active plan and one canonical active report.
- Dated/dispersed adjunct plans should be marked `historical-superseded` with canonical pointers.
- Cross-directory test analysis closure should reference at least one unit, integration, and contract/architecture suite from `contextual_system_manifest.yaml`.

## MOS Post-Closure Evidence Links

- `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md`
- `docs/audits/reports/mos_system_surface_visualization_reflectivity_report_2026-04-22.md`
- `docs/audits/reports/mos_cutover_intent_integrity_report_2026-04-22.md`
- `docs/audits/reports/mos_premorice_and_modularization_posture_report_2026-04-22.md`
- `docs/plans/mos_post_closure_consolidation_plan_2026-04-21.md`
- `docs/plans/mos_novelty_positioning_follow_on_2026-04-21.md`
- `docs/plans/workbench_ui_hardening_follow_on_2026-04-21.md`

## Rule

Use YAML manifest + task board as first authority for status and closure; use markdown
plans for narrative implementation detail and deep rationale.
