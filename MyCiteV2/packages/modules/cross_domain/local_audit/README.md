# Local Audit

Authority: [../../../../docs/plans/authority_stack.md](../../../../docs/plans/authority_stack.md)

`packages/modules/cross_domain/local_audit/` owns the MVP local-audit semantic boundary.

Implemented in this phase:

- normalized local-audit record policy
- forbidden-key and secret-key rejection
- append handoff through `AuditLogPort`
- read-by-id handoff through `AuditLogPort`

Not implemented in this phase:

- filesystem layout
- runtime composition
- broad logging or event semantics
- external-events behavior
