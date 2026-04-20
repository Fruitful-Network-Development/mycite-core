# Audits

The active audit baseline is the one-shell portal model. Older split-shell
audits were removed because they no longer describe the repository truth.

Latest follow-up:

- `portal_shell_hardening_2026-04-15.md` records the hydration-flash fix, the Interface Panel collapse correction (with legacy `inspector` compatibility), the control-panel padding fix, and the shared shell asset manifest contract.
- `portal_shell_peer_region_normalization_2026-04-15.md` records the peer-region terminology normalization, additive interface-panel compatibility aliases, workbench toggle behavior, and the shared root/tool posture contract.
- `portal_shell_menu_lock_and_containment_2026-04-15.md` records icon-toggle menubar normalization, tool-only double-click lock posture, and containment fixes for full-width interface-panel rendering.
- `cts_gis_legacy_maps_phase_a_alignment_2026-04-16.md` records phase-A CTS-GIS legacy-`maps` alias centralization, canonical storage migration, and the v2.5.4 hard-removal target.
- `cts_gis_phase_b_canonical_removal_2026-04-16.md` records v2.5.4 hard-removal of legacy CTS-GIS aliases and the canonical-only runtime/API contract.

Foundation-first status:

- `cts_gis_hops_first_stage_b_post_2026-04-19.*` was removed because it was a no-op post-verification snapshot and no longer carried unique audit value.
- `reports/core_portal_datum_mss_protocol_report_2026-04-16.md` is historical evidence; its publication-domain, write-result schema, malformed `surface_query`, and NETWORK warning findings are now closed in code.
- `reports/interface_surface_unification_report_2026-04-16.md` is partially historical; the tool-posture, NETWORK query-normalization, browser-posture, CTS-GIS query/body guardrail, and route-scope lock-state gaps are now closed in code, while only low-priority compatibility/documentation guardrails remain deferred.
- `reports/package_modularization_report_2026-04-16.md` is partially historical; the filesystem-adapter failures no longer reproduce in the active repo, and the remaining worthwhile cleanup in this pass is low-cost boundary noise only.
- `reports/tools_ui_implementation_mismatch_report_2026-04-16.md` is partially historical; the shared tool surface adapter, wrapped fallback states, and direct surface-request helper are already present in the shell static bundle.
- `cts_gis_platform_hardening_audit_2026-04-20.md` is now historical evidence for the CTS-GIS platform pass; Summit Stage-A cleanup is closed by `cts_gis_summit_repair_followup_2026-04-20.*`, which reports `0 flagged / 32 clean` across the repo and state data roots.
