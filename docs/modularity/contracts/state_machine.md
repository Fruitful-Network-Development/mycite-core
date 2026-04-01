# State Machine

- Owns: shell/workbench state transitions, reducers, activation policies, staged
  mutation rules.
- Does not own: filesystem path derivation, contract storage, tool-specific
  business data.
- Reads: selected-context payloads, sandbox/workbench state.
- Writes: in-memory or explicit staged state surfaces only.
- Depends on: `portal_core/shell`, `portal_core/sandboxes`.
- Depended on by: shell/workbench routes and future tool mediation flows.

