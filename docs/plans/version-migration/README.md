# V1 Migration

Authority order for this directory is subordinate to the v2 ontology, ADRs,
phase docs, and active post-MVP planning surfaces. See
[../v2-authority_stack.md](../v2-authority_stack.md).

Use this directory to answer:

- what v1 contains
- what drift patterns must not return
- which concepts should be recreated
- which v1 areas must be split before recreation
- which sources are evidence only
- what remains in scope for V1 retirement review

Do not use this directory as the active live cutover work queue. For the
current post-cutover hardening path, use
[../post_mvp_rollout/post_aws_tool_platform/v2_native_cutover_hardening.md](../post_mvp_rollout/post_aws_tool_platform/v2_native_cutover_hardening.md).
Use
[../post_mvp_rollout/post_aws_tool_platform/v1_retirement_execution_ledger.md](../post_mvp_rollout/post_aws_tool_platform/v1_retirement_execution_ledger.md)
for the active removal/quarantine pass, and
[../phases/11_cleanup_and_v1_retirement_review.md](../phases/11_cleanup_and_v1_retirement_review.md)
for the formal exit gate.

## Current long-term sequence

1. finish V2-native hardening
2. resolve the V1 retirement execution ledger
3. close the Phase 11 retirement review
4. only then reopen deferred client-visible or later tool planning

## Canonical documents

- [hanus_interface_analysis.md](hanus_interface_analysis.md)
- [mycite_v2_structure_report.md](mycite_v2_structure_report.md)
- [mycite2_migration_plan.md](mycite2_migration_plan.md)
- [v1_audit_map.md](v1_audit_map.md)
- [v1_retention_vs_recreation.md](v1_retention_vs_recreation.md)
- [source_authority_index.md](source_authority_index.md)
- [v1_drift_ledger.md](v1_drift_ledger.md)
- [recreation_sequence.md](recreation_sequence.md)

Historical numbered drafts are preserved in [historical/](historical/) but are not the primary v2 surface anymore.
