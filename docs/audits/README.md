# Audits

Use this directory as part of the same unified control system used by `docs/plans/`.

## Start Here

- Context manifest: `docs/plans/contextual_system_manifest.yaml`
- Context task board: `docs/plans/contextual_system_task_board.yaml`
- Operating guide: `docs/plans/planning_audit_operating_system.md`
- Compatibility manifest/task board:
  - `docs/plans/planning_audit_manifest.yaml`
  - `docs/plans/planning_task_board.yaml`
- Report index: `docs/audits/reports/README.md`

## Canonical Active Audit Plans

- `cts_gis_open_alignment_audit_plan_2026-04-23.md` (canonical CTS-GIS open queue)
- `aws_csm_operating_alignment_audit_plan_2026-04-23.md` (canonical AWS-CSM alignment stream)
- `performance_weight_speed_audit_plan_2026-04-16.md`

## Consolidated / Historical Planning Artifacts

The following remain as deep-detail history and are no longer canonical active entrypoints:

- `cts_gis_source_hops_audit_plan_2026-04-20.md`
  - lifecycle: `historical-superseded`
  - canonical replacement: `cts_gis_open_alignment_audit_plan_2026-04-23.md`
- `cts_gis_samras_rule_alignment_audit_plan_2026-04-20.md`
  - lifecycle: `historical-superseded`
  - canonical replacement: `cts_gis_open_alignment_audit_plan_2026-04-23.md`
- `cts_gis_datum_handling_alignment_audit_plan_2026-04-20.md`
  - lifecycle: `historical-superseded`
  - canonical replacement: `cts_gis_open_alignment_audit_plan_2026-04-23.md`

Completed MOS planning artifacts are archived under `docs/audits/archive/` with
their corresponding closure evidence retained in `docs/audits/reports/`.

## Rule

Audit execution and closure status should be updated in the YAML manifest/task board
first, then reflected in markdown plan/report narratives.

Canonical contextual order:

1. contextual manifest/task board
2. compatibility manifest/task board
3. markdown plan/audit/report narratives

## MOS Post-Closure Report Anchors

- `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md`
- `docs/audits/reports/mos_personal_notes_to_canon_crosswalk_2026-04-21.md`
- `docs/audits/reports/mos_documentation_supersession_audit_2026-04-21.md`
- `docs/audits/reports/mos_system_surface_visualization_reflectivity_report_2026-04-22.md`
- `docs/audits/reports/mos_cutover_intent_integrity_report_2026-04-22.md`
- `docs/audits/reports/mos_premorice_and_modularization_posture_report_2026-04-22.md`
- `docs/audits/reports/workbench_ui_utilitarian_design_audit_2026-04-21.md`
