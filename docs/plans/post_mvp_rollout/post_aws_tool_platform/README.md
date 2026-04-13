# Post-AWS Tool Platform

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This subtree defines the stabilized shared platform after the AWS read-only and
AWS narrow-write slices are complete.

Use this subtree for two things:

- current platform contracts that future tools must obey
- retained posture and proof for the canonical V2 closure sequence

## Platform status

`Post-AWS Tool Platform Stabilization And V2 Cutover Readiness` is complete at the runtime/platform level when:

- the shell-owned tool descriptor shape is fixed in `packages/state_machine/hanus_shell/admin_shell.py`
- the shared runtime entrypoint catalog is fixed in `instances/_shared/runtime/runtime_platform.py`
- admin runtime responses use the shared runtime envelope helper
- read-only and bounded-write slice patterns are documented and tested

Current live posture:

- V2-native portal host is the live `/portal` surface for FND and TFF.
- Shape B bridge work is historical cutover evidence, not the default shape for new work.
- Canonical live AWS profile mapping remains current and must stay aligned with the deployed V2 host.
- The V1 retirement ledger and Phase 11 gate are closed through [../../../records/22-v1_retirement_closure.md](../../../records/22-v1_retirement_closure.md).
- Current shell-registered admin-tool entries are `aws`, `aws_narrow_write`,
  `aws_csm_sandbox`, `aws_csm_onboarding`, `cts_gis`, and `fnd_ebi`.
- Current config-gated live exposure keeps `cts_gis` and `fnd_ebi` enabled on
  FND only while TFF remains hidden and blocked for both.

## Use order

1. Read [tool_descriptor_contract.md](tool_descriptor_contract.md).
2. Read [runtime_entrypoint_catalog.md](runtime_entrypoint_catalog.md).
3. Read [runtime_envelope_and_launch_results.md](runtime_envelope_and_launch_results.md).
4. Read [read_only_and_bounded_write_patterns.md](read_only_and_bounded_write_patterns.md).
5. Read [future_tool_drop_in_contract.md](future_tool_drop_in_contract.md).
6. Read [../../../records/22-v1_retirement_closure.md](../../../records/22-v1_retirement_closure.md) for the formal closure of the V1 retirement sequence.
7. Read [v2_native_cutover_hardening.md](v2_native_cutover_hardening.md) only when the work needs the underlying closure packet details.
8. Read [v1_retirement_execution_ledger.md](v1_retirement_execution_ledger.md) only when the work needs the resolved residue ledger.
9. Read [../../../contracts/portal_auth_and_audience_boundary.md](../../../contracts/portal_auth_and_audience_boundary.md) when the work changes browser auth, trusted headers, or audience checks.
10. Read [v2_admin_cutover_readiness.md](v2_admin_cutover_readiness.md) for current posture.
11. Read [live_state_authority_and_mapping.md](live_state_authority_and_mapping.md) for canonical live AWS mapping rules.
12. Read [deployment_bridge_contract.md](deployment_bridge_contract.md) and [cutover_execution_sequence.md](cutover_execution_sequence.md) only as historical cutover design and sequencing evidence.
13. Use [../slice_registry/admin_band0_v2_deployment_bridge.md](../slice_registry/admin_band0_v2_deployment_bridge.md) only as a record-linked slice history.
14. Read [../../v2.3-tool_exposure_and_admin_activity_bar_alignment.md](../../v2.3-tool_exposure_and_admin_activity_bar_alignment.md) when the work needs the proposed V2 config-gate layer above the shell-owned registry.
15. Read [../../v2.3-tool_surface_packet/aws_csm.md](../../v2.3-tool_surface_packet/aws_csm.md), [../../v2.3-tool_surface_packet/fnd_ebi.md](../../v2.3-tool_surface_packet/fnd_ebi.md), and [../../v2.3-tool_surface_packet/cts_gis.md](../../v2.3-tool_surface_packet/cts_gis.md) for the narrowed next-family queue.

## Non-negotiable rules

- The shell owns discoverability and launch legality.
- Runtime entrypoints compose only.
- Tool descriptors are catalog-driven and deny-by-default.
- No dynamic package scan is authoritative.
- No direct provider route may replace the v2 admin shell.
- AWS is the reference implementation for read-only and bounded-write patterns, not a broad provider-admin template.
- Root-level V1 compatibility package paths must not be recreated for V2 cutover.
- Live V2 writes must target one canonical live artifact, not a generated shadow snapshot.
- New work must not extend bridge-only surfaces when the V2-native host already owns the live boundary.
- Future tool drop-in work may resume only through the reopened slice order in
  [../current_planning_index.md](../current_planning_index.md); bridge-era
  surfaces do not reopen as an alternate track.
- Family-root packet docs now narrow later tool work into one canonical family
  plus subordinate slices/crosswalks, rather than reopening fragmented root
  tool names.
