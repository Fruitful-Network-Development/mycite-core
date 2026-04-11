# Runtime

Authority: [../../../../docs/plans/v2-authority_stack.md](../../../../docs/plans/v2-authority_stack.md)

`instances/_shared/runtime/` owns shared runtime composition only.

Implemented in shared runtime:

- one shared admin runtime descriptor catalog and envelope helper
- one composition entrypoint for the `Shell Action To Local Audit` slice
- one composition entrypoint for `Admin Band 0 Internal Admin Replacement`
- one composition entrypoint for `admin_band1.aws_read_only_surface`
- one composition entrypoint for `admin_band2.aws_narrow_write_surface`

Not implemented in shared runtime:

- flavor-specific runtime composition
- tools
- sandboxes
- provider-admin replacement slices beyond the internal admin band
