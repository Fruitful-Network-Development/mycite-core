# Runtime

Authority: [../../../../docs/contracts/portal_shell_contract.md](../../../../docs/contracts/portal_shell_contract.md)

`instances/_shared/runtime/` owns shared runtime composition only.

Implemented in shared runtime:

- one shared portal runtime descriptor catalog and envelope helper
- one shell entrypoint for SYSTEM, NETWORK, and UTILITIES root surfaces
- one shell entrypoint family for SYSTEM child surfaces
- one tool runtime family for SYSTEM tool work pages
- one utility surface family for tool exposure and integration state
- one local-audit composition path for normalized portal-shell requests

Not implemented in shared runtime:

- flavor-specific runtime composition
- sandboxes
- broad datum mutation or repair flows
