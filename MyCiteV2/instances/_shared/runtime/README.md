# Runtime

Authority: [../../../../docs/plans/v2-authority_stack.md](../../../../docs/plans/v2-authority_stack.md)

`instances/_shared/runtime/` owns shared runtime composition only.

Implemented in shared runtime:

- one shared admin runtime descriptor catalog and envelope helper
- one composition entrypoint for the `Shell Action To Local Audit` slice
- one composition entrypoint for `Admin Band 0 Internal Admin Replacement`
- one composition entrypoint for `admin_band1.aws_read_only_surface`
- one composition entrypoint for `admin_band2.aws_narrow_write_surface`
- one composition path for the admin datum workbench surface using authoritative datum documents plus read-only recognition diagnostics
- one composition entrypoint for `band1.portal_home_tenant_status`
- one composition entrypoint for `band1.operational_status_surface`
- one composition entrypoint for `band1.audit_activity_visibility`
- one composition entrypoint for `band2.profile_basics_write_surface`

Not implemented in shared runtime:

- flavor-specific runtime composition
- tools
- sandboxes
- broad datum mutation or repair flows
