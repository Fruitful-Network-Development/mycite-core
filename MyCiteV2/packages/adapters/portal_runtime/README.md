# Portal Runtime Adapter

Authority: [../../../../docs/plans/v2-authority_stack.md](../../../../docs/plans/v2-authority_stack.md)

`packages/adapters/portal_runtime/` currently contains quarantined bridge-era
transport adapters retained for V1 retirement review.

The canonical live V2 host is
`MyCiteV2/instances/_shared/portal_host/`, not this package.

The package root is intentionally not an active import surface. Historical
replay or record-only tests must import `v1_host_bridge.py` directly.

Implemented:

- Shape B V1-host bridge registration in `v1_host_bridge.py`
- explicit compatibility routes for `admin.shell_entry`, `admin.aws.read_only`, and `admin.aws.narrow_write`
- readiness payload that reports configured inputs without exposing filesystem paths

Not canonical here:

- the live `/portal` host boundary
- new browser auth or audience ownership rules
- new client-visible tool work
- any default import surface for active V2 adapters
