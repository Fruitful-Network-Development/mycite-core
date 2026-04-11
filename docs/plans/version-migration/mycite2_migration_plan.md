# MyCite2 Migration Plan

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

This file keeps the historical title `MyCite2` only because it names a preexisting synthesis surface. In v2 prose, the normalized term is `MyCiteV2`.

This document supersedes [historical/3-Migration.md](historical/3-Migration.md).

## Migration rule

Migration means recreation under v2 ontology, not relocation of v1 files.

## Ordered migration posture

1. Fix ontology and authority first
2. Recreate pure core
3. Recreate shell/state-machine contracts
4. Define ports
5. Recreate domain and cross-domain modules
6. Implement adapters
7. Recreate tools
8. Recreate sandboxes as orchestration
9. Compose runtime
10. Run integration and boundary checks
11. Review v1 retirement

## Current execution note

The ordered posture above defines the reconstruction doctrine. The current
active execution sequence is now:

1. [../post_mvp_rollout/post_aws_tool_platform/v2_native_cutover_hardening.md](../post_mvp_rollout/post_aws_tool_platform/v2_native_cutover_hardening.md)
2. [../post_mvp_rollout/post_aws_tool_platform/v1_retirement_execution_ledger.md](../post_mvp_rollout/post_aws_tool_platform/v1_retirement_execution_ledger.md)
3. [../phases/11_cleanup_and_v1_retirement_review.md](../phases/11_cleanup_and_v1_retirement_review.md)

Do not treat deferred follow-on slices or future tool tracks as parallel
alternatives to this sequence.

## Hard cuts

- Do not import v1 modules into v2.
- Do not preserve ambiguous names when the ontology has been clarified.
- Do not let compatibility wrappers define v2 structure.
