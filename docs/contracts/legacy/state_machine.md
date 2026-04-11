# State Machine

- Owns: shell/workbench state transitions, reducers, activation policies, staged
  mutation rules.
- Does not own: filesystem path derivation, contract storage, tool-specific
  business data.
- Reads: selected-context payloads, sandbox/workbench state.
- Writes: in-memory or explicit staged state surfaces only.
- Depends on: `mycite_core/state_machine`, `mycite_core/mss_resolution`.
- Depended on by: shell/workbench routes and future tool mediation flows.
