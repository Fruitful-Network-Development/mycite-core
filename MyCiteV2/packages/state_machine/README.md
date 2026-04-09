# State Machine

Authority: [../../docs/plans/authority_stack.md](../../docs/plans/authority_stack.md)

`packages/state_machine/` owns shell legality, AITAS vocabulary, NIMM directives, Hanus shell behavior, and mediation surface behavior.

Implemented for the MVP so far:

- minimal `aitas` attention and intention contracts
- minimal `nimm` directive normalization
- minimal `hanus_shell` action, state, reducer, and result contracts

Deferred in this phase:

- `mediation_surface` behavior
- tool attachment logic
- sandbox orchestration logic
- host or runtime composition logic
