# V1 Retirement Closure

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

Closure date: `2026-04-11`

This record closes the canonical V2 retirement sequence for V1.

## Final statement

`MyCiteV1/` remains in the repository as historical evidence only. It is not a
current implementation dependency, deployment dependency, or planning template
for canonical V2.

## Closure outcomes

- The live `/portal` boundary is the V2-native host under `MyCiteV2/instances/_shared/portal_host/`.
- Tracked deployment truth lives in `srv-infra`, not in bridge-era repo memory or V1 unit names.
- The V1-host bridge mount has been removed from the FND and TFF V1 apps.
- `MyCiteV2/packages/adapters/portal_runtime/v1_host_bridge.py` is retained only as a quarantined direct-path artifact for historical replay.
- `MyCiteV2/packages/adapters/portal_runtime/__init__.py` no longer exports bridge symbols as a normal adapter surface.
- Bridge-specific tests are historical-only and require `MYCITE_ENABLE_HISTORICAL_BRIDGE_TESTS=1`.
- Bridge-era planning docs remain as record-only evidence and no longer present Shape B as an active implementation option.

## Residue classification

- `MyCiteV1/`: `historical_only`
- `MyCiteV2/packages/adapters/portal_runtime/v1_host_bridge.py`: `quarantine`
- `MyCiteV2/tests/*bridge*`: `historical_only`
- bridge and cutover records under `docs/records/`: `historical_only`

## Canonical next sequence

Follow-on planning resumes in this order:

1. `band1_portal_home_tenant_status`
2. `band1_operational_status_surface`
3. `band1_audit_activity_visibility`
4. `band2_profile_basics_write_surface`
5. Maps
6. AGRO-ERP

Use [../plans/post_mvp_rollout/current_planning_index.md](../plans/post_mvp_rollout/current_planning_index.md)
as the active entrypoint for that reopened sequence.

## Supporting proof

- [../plans/post_mvp_rollout/post_aws_tool_platform/v1_retirement_execution_ledger.md](../plans/post_mvp_rollout/post_aws_tool_platform/v1_retirement_execution_ledger.md)
- [../plans/phases/11_cleanup_and_v1_retirement_review.md](../plans/phases/11_cleanup_and_v1_retirement_review.md)
- [15-cut_over.md](15-cut_over.md)
- [16-v2_native_portal_cutover.md](16-v2_native_portal_cutover.md)
