# Post-AWS Tool Platform

Authority: [../../authority_stack.md](../../authority_stack.md)

This subtree defines the stabilized shared platform after the AWS read-only and AWS narrow-write slices are complete.

Use this subtree before building any post-AWS tool such as Maps or AGRO-ERP.

## Platform status

`Post-AWS Tool Platform Stabilization And V2 Cutover Readiness` is complete when:

- the shell-owned tool descriptor shape is fixed in `packages/state_machine/hanus_shell/admin_shell.py`
- the shared runtime entrypoint catalog is fixed in `instances/_shared/runtime/runtime_platform.py`
- admin runtime responses use the shared runtime envelope helper
- read-only and bounded-write slice patterns are documented and tested
- v2 is the operational admin portal base for future tool work

## Use order

1. Read [tool_descriptor_contract.md](tool_descriptor_contract.md).
2. Read [runtime_entrypoint_catalog.md](runtime_entrypoint_catalog.md).
3. Read [runtime_envelope_and_launch_results.md](runtime_envelope_and_launch_results.md).
4. Read [read_only_and_bounded_write_patterns.md](read_only_and_bounded_write_patterns.md).
5. Read [future_tool_drop_in_contract.md](future_tool_drop_in_contract.md).
6. Read [v2_admin_cutover_readiness.md](v2_admin_cutover_readiness.md).

## Non-negotiable rules

- The shell owns discoverability and launch legality.
- Runtime entrypoints compose only.
- Tool descriptors are catalog-driven and deny-by-default.
- No dynamic package scan is authoritative.
- No direct provider route may replace the v2 admin shell.
- AWS is the reference implementation for read-only and bounded-write patterns, not a broad provider-admin template.
