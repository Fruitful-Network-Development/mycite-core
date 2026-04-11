# Portal Rollout Bands

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

This file defines the only approved exposure progression for post-MVP portal work.

## Current status

- Current exposure band: `Band 0 Internal Only`.
- Current planning and specification target: `Band 1 Trusted-Tenant Read-Only`.
- No band may be skipped.

## Global rules

- Every slice must name a rollout band before implementation.
- Read-only slices come before writable slices.
- One vertical slice is preferred over broad partial parity.
- Runtime composition remains thin in every band.
- Tools and sandboxes are not assumed to be part of the next band.

## Admin-first overlay

Operational replacement of the old admin portal uses the nested admin-first track in [admin_first/admin_first_rollout_band.md](admin_first/admin_first_rollout_band.md).

- `Admin Band 0` nests under `Band 0 Internal Only`.
- `Admin Band 1` nests under `Band 1 Trusted-Tenant Read-Only`.
- `Admin Band 2` nests under `Band 2 Trusted-Tenant Writable Slice`.

That track does not bypass the global bands. It specifies the order for admin shell, registry, AWS, Maps, and AGRO work inside them.

## Band 0: Internal Only

Audience:
- internal builders only

Purpose:
- prove architecture
- verify runtime composition
- establish slice registry and exposure gates

Allowed work:
- internal proving paths
- architecture boundary tests
- slice specification work
- internal observability needed to support Band 1 planning

Forbidden drift:
- trusted-tenant exposure
- writable client workflows
- flavor expansion
- tool or sandbox rollout

Exit criteria:
- MVP acceptance criteria pass
- runtime entrypoint catalog exists
- slice registry exists
- client exposure gates are defined
- first Band 1 slice candidates are specified

## Band 1: Trusted-Tenant Read-Only

Audience:
- a very small set of trusted tenants or client representatives

Purpose:
- expose narrow read-only operating surfaces safely
- validate that the portal can be client-visible without write risk

Allowed slice types:
- portal home and tenant status
- audit and activity visibility
- narrow operational status

Forbidden drift:
- write workflows
- contract editing
- reference workbench flows
- tools
- sandboxes
- provider-specific admin surfaces

Exit criteria:
- at least one Band 1 slice passes its slice gate
- no Band 1 slice relies on flavor-specific runtime code
- no Band 1 slice introduces hidden write actions
- Band 2 writable candidate is explicitly specified before any write implementation begins

## Band 2: Trusted-Tenant Writable Slice

Audience:
- trusted tenants only

Purpose:
- expose exactly one narrow writable workflow at a time

Allowed slice types:
- one bounded client-value write workflow with explicit rollback and audit

Forbidden drift:
- multiple writable slices in parallel
- broad portal editing
- hidden write side effects
- provider-admin workflow bundling
- tool or sandbox rollout

Exit criteria:
- Band 1 slices are stable enough to remain client-visible while the writable slice is introduced
- the writable slice passes its slice gate
- read-after-write and audit behavior are proven end to end
- rollback and recovery steps are documented

## Band 3: Broader Client Rollout

Audience:
- broader client exposure beyond the initial trusted set

Purpose:
- expand client access only after repeatable success in the lower bands

Allowed slice types:
- already-proven read-only slices
- already-proven writable slice patterns adapted carefully

Forbidden drift:
- bundling unproven slices into the broader rollout
- using broader rollout as a substitute for missing slice gates
- flavor expansion by convenience

Exit criteria:
- explicit future decision required
- not in scope for the current operating band
