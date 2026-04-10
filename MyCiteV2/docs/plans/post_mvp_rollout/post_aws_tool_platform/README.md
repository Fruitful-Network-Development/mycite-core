# Post-AWS Tool Platform

Authority: [../../authority_stack.md](../../authority_stack.md)

This subtree defines the stabilized shared platform after the AWS read-only and AWS narrow-write slices are complete.

Use this subtree before building any post-AWS tool such as Maps or AGRO-ERP.

## Platform status

`Post-AWS Tool Platform Stabilization And V2 Cutover Readiness` is complete at the runtime/platform level when:

- the shell-owned tool descriptor shape is fixed in `packages/state_machine/hanus_shell/admin_shell.py`
- the shared runtime entrypoint catalog is fixed in `instances/_shared/runtime/runtime_platform.py`
- admin runtime responses use the shared runtime envelope helper
- read-only and bounded-write slice patterns are documented and tested

Live deployment cutover is a separate deployment bridge step. V2 is not the live `/portal` web host until [deployment_bridge_contract.md](deployment_bridge_contract.md), [live_state_authority_and_mapping.md](live_state_authority_and_mapping.md), and [cutover_execution_sequence.md](cutover_execution_sequence.md) are satisfied.

## Use order

1. Read [tool_descriptor_contract.md](tool_descriptor_contract.md).
2. Read [runtime_entrypoint_catalog.md](runtime_entrypoint_catalog.md).
3. Read [runtime_envelope_and_launch_results.md](runtime_envelope_and_launch_results.md).
4. Read [read_only_and_bounded_write_patterns.md](read_only_and_bounded_write_patterns.md).
5. Read [future_tool_drop_in_contract.md](future_tool_drop_in_contract.md).
6. Read [v2_admin_cutover_readiness.md](v2_admin_cutover_readiness.md).
7. For live `/portal` cutover, read [deployment_bridge_contract.md](deployment_bridge_contract.md).
8. For FND/TFF state mapping, read [live_state_authority_and_mapping.md](live_state_authority_and_mapping.md).
9. For implementation order, read [cutover_execution_sequence.md](cutover_execution_sequence.md).
10. Use [../slice_registry/admin_band0_v2_deployment_bridge.md](../slice_registry/admin_band0_v2_deployment_bridge.md) as the bridge slice.

## Non-negotiable rules

- The shell owns discoverability and launch legality.
- Runtime entrypoints compose only.
- Tool descriptors are catalog-driven and deny-by-default.
- No dynamic package scan is authoritative.
- No direct provider route may replace the v2 admin shell.
- AWS is the reference implementation for read-only and bounded-write patterns, not a broad provider-admin template.
- Root-level V1 compatibility package paths must not be recreated for V2 cutover.
- Live V2 writes must target one canonical live artifact, not a generated shadow snapshot.
