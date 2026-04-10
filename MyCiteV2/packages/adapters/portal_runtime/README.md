# Portal Runtime Adapter

Authority: [../../../docs/plans/authority_stack.md](../../../docs/plans/authority_stack.md)

`packages/adapters/portal_runtime/` owns portal-host transport adapters for V2 runtime entrypoints.

Implemented:

- Shape B V1-host bridge registration in `v1_host_bridge.py`
- explicit routes for `admin.shell_entry`, `admin.aws.read_only`, and `admin.aws.narrow_write`
- readiness payload that reports configured inputs without exposing filesystem paths

Not implemented here:

- V1 route parity
- dynamic package discovery
- Maps or AGRO-ERP bridge routes
- generated V2 shadow state
