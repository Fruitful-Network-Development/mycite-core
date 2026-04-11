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
- which retained V1 materials still matter as lower-precedence migration evidence

Do not use this directory as the active live cutover or retirement work queue.
The canonical V2 retirement sequence is already closed through
[../records/22-v1_retirement_closure.md](../records/22-v1_retirement_closure.md).

## Retirement status

1. V2-native hardening is complete.
2. The V1 retirement execution ledger is resolved.
3. Phase 11 retirement review is closed.
4. Follow-on planning resumes from the reopened Band 1 sequence in
   [../post_mvp_rollout/current_planning_index.md](../post_mvp_rollout/current_planning_index.md).

## Post-closure entrypoints

- Use [../records/22-v1_retirement_closure.md](../records/22-v1_retirement_closure.md)
  for the formal closure statement.
- Use [../post_mvp_rollout/current_planning_index.md](../post_mvp_rollout/current_planning_index.md)
  for the active post-retirement work queue.
- Use [../post_mvp_rollout/post_aws_tool_platform/v2_native_cutover_hardening.md](../post_mvp_rollout/post_aws_tool_platform/v2_native_cutover_hardening.md)
  only when you need the completed closure packet details.
- Use [../post_mvp_rollout/post_aws_tool_platform/v1_retirement_execution_ledger.md](../post_mvp_rollout/post_aws_tool_platform/v1_retirement_execution_ledger.md)
  only when you need the resolved residue dispositions.
- Use [../phases/11_cleanup_and_v1_retirement_review.md](../phases/11_cleanup_and_v1_retirement_review.md)
  only when you need the completed retirement gate wording.

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
