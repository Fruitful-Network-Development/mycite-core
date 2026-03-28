# Shared Tool Packages

This directory is the canonical home for situational tool-business logic that is
not part of the core service shell runtime.

Current portal instances may still contain thin wrapper modules under
`portal/tools/<tool_id>/__init__.py`; those wrappers should delegate logic to
shared package modules in this directory.

Planned package moves:
- `paypal_tenant_actions`
- `fnd_provisioning`
- `operations`
