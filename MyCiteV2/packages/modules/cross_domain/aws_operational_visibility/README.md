# AWS Operational Visibility

Authority: [../../../../docs/plans/authority_stack.md](../../../../docs/plans/authority_stack.md)

`packages/modules/cross_domain/aws_operational_visibility/` owns the semantic policy for the first AWS read-only admin slice.

Implemented in this slice:

- normalization of one tenant-scoped AWS operational status source
- secret-bearing key rejection
- canonical newsletter operational profile summary
- compatibility warning derivation
- read-only service handoff to the AWS read-only status port

Not implemented in this slice:

- AWS provisioning writes
- manual newsletter send
- raw credential display
- multi-provider admin aggregation
