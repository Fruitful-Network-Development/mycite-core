# Runtime

Authority: [../../../docs/plans/authority_stack.md](../../../docs/plans/authority_stack.md)

`instances/_shared/runtime/` owns shared runtime composition only.

Implemented for the MVP:

- one composition entrypoint for the `Shell Action To Local Audit` slice
- one composition entrypoint for `Admin Band 0 Internal Admin Replacement`

Not implemented for the MVP:

- flavor-specific runtime composition
- tools
- sandboxes
- provider-admin replacement slices beyond the internal admin band
