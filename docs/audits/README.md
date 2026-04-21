# Audits

The active audit baseline is the one-shell portal model. Older split-shell
audits were removed because they no longer describe the repository truth.

Completed audits (report/evidence retained, planning docs removed):

- `portal_shell_hardening_2026-04-15.md` records the hydration-flash fix, the Interface Panel collapse correction (with legacy `inspector` compatibility), the control-panel padding fix, and the shared shell asset manifest contract.
- `portal_shell_peer_region_normalization_2026-04-15.md` records the peer-region terminology normalization, additive interface-panel compatibility aliases, workbench toggle behavior, and the shared root/tool posture contract.
- `portal_shell_menu_lock_and_containment_2026-04-15.md` records icon-toggle menubar normalization, tool-only double-click lock posture, and containment fixes for full-width interface-panel rendering.
- `cts_gis_legacy_maps_phase_a_alignment_2026-04-16.md` records phase-A CTS-GIS legacy-`maps` alias centralization, canonical storage migration, and the v2.5.4 hard-removal target.
- `cts_gis_phase_b_canonical_removal_2026-04-16.md` records v2.5.4 hard-removal of legacy CTS-GIS aliases and the canonical-only runtime/API contract.
- `reports/mos_fnd_sql_ingestion_coverage_report_2026-04-21.md` records authoritative FND SQL ingestion coverage for the final MOS cut-over.
- `reports/mos_sql_only_authority_activation_and_legacy_retirement_2026-04-21.md` records shared-runtime SQL-only activation and retirement of filesystem datum/audit authority from migrated SYSTEM surfaces.
- `reports/mos_directive_context_non_inference_validation_2026-04-21.md` records the additive-only, explicit-manifest-only directive-context import posture.
- `reports/mos_documentation_alignment_and_cleanup_2026-04-21.md` records active-doc alignment and historical-artifact cleanup for the completed MOS program.
- `reports/mos_program_closure_report_2026-04-21.md` records the final authoritative MOS cut-over closure statement.

Foundation-first status:

- `cts_gis_hops_first_stage_b_post_2026-04-19.*` was removed because it was a no-op post-verification snapshot and no longer carried unique audit value.
- `core_portal_datum_mss_protocol_audit_plan_2026-04-16.md`, `interface_surface_unification_audit_plan_2026-04-16.md`, and `tools_ui_implementation_audit_plan_2026-04-16.md` were removed after their paired reports became the canonical retained evidence.
- `package_modularization_audit_plan_2026-04-16.md` and `peripheral_packages_modularization_audit_plan_2026-04-16.md` were removed after completion evidence was consolidated into their paired reports.
- `desktop_access_and_historical_drift_audit_plan_2026-04-16.md` was removed after remaining high-priority work (`DM-02`, `DM-04`) moved to the active implementation plan at `docs/plans/desktop_dm02_dm04_reconciliation_plan_2026-04-20.md`.
- `documentation_agent_yaml_optimization_plan_2026-04-16.md` is retained only as a historical bridge document; the active execution set remains `docs/standards/*`, `docs/plans/documentation_ia_remediation_backlog.md`, and `docs/audits/reports/documentation_ia_audit_report_2026-04-20.md`.
- `reports/core_portal_datum_mss_protocol_report_2026-04-16.md` is historical evidence; its publication-domain, write-result schema, malformed `surface_query`, and NETWORK warning findings are now closed in code.
- `reports/interface_surface_unification_report_2026-04-16.md` is partially historical; the tool-posture, NETWORK query-normalization, browser-posture, CTS-GIS query/body guardrail, and route-scope lock-state gaps are now closed in code, while only low-priority compatibility/documentation guardrails remain deferred.
- `reports/package_modularization_report_2026-04-16.md` is partially historical; the filesystem-adapter failures no longer reproduce in the active repo, and the remaining worthwhile cleanup in this pass is low-cost boundary noise only.
- `reports/tools_ui_implementation_mismatch_report_2026-04-16.md` is partially historical; the shared tool surface adapter, wrapped fallback states, and direct surface-request helper are already present in the shell static bundle.
- `cts_gis_platform_hardening_audit_2026-04-20.md` is now historical evidence for the CTS-GIS platform pass; Summit Stage-A cleanup is closed by `cts_gis_summit_repair_followup_2026-04-20.*`, which reports `0 flagged / 32 clean` across the repo and state data roots.
- `reports/documentation_ia_audit_report_2026-04-20.md` captures the documentation IA + agent YAML baseline remediation pass and remaining migration/enforcement backlog.

Still useful and not yet fully completed:

- `performance_weight_speed_audit_plan_2026-04-16.md` with active report `reports/performance_weight_speed_report_2026-04-16.md` (measurement and execution phases still open).
- `docs/plans/desktop_dm02_dm04_reconciliation_plan_2026-04-20.md` now governs remaining desktop deep-link and scoped shell-state persistence work from `reports/desktop_access_historical_drift_report_2026-04-16.md`.
- `docs/plans/documentation_ia_remediation_backlog.md` now governs remaining documentation IA/YAML migration and CI-enforcement expansion from `reports/documentation_ia_audit_report_2026-04-20.md`.
- `docs/plans/master_plan_mos.md` is now the completed authoritative closure record for the MOS SQL cut-over program; follow-on MOS work should use supporting plans or audits rather than creating a competing master-plan document.
- `cts_gis_source_hops_audit_plan_2026-04-20.md` remains useful until all listed Summit lineage files are either `verified` or explicitly `blocked` with rationale.
- `cts_gis_samras_rule_alignment_audit_plan_2026-04-20.md` defines SAMRAS structural/mutation/mediation rule investigation and alignment gates.
- `cts_gis_datum_handling_alignment_audit_plan_2026-04-20.md` defines datum-file/source-file handling, ordering/editing, MSS-form compatibility, and modularization alignment as a top-priority audit track.
