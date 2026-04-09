# Filesystem Adapter

Authority: [../../../docs/plans/authority_stack.md](../../../docs/plans/authority_stack.md)

`packages/adapters/filesystem/` owns filesystem-backed port implementations only.

Implemented in this phase:

- one narrow `AuditLogPort` implementation backed by one caller-supplied NDJSON file
- one narrow AWS read-only status adapter backed by one caller-supplied JSON snapshot file

Not implemented in this phase:

- runtime path selection
- instance-led directory layout
- local-audit semantic validation
- AWS operational-visibility semantic validation
- broader filesystem framework behavior
