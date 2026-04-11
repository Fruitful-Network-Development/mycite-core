# State Machine

Authority: [../../../docs/plans/v2-authority_stack.md](../../../docs/plans/v2-authority_stack.md)

`packages/state_machine/` owns shell legality, AITAS vocabulary, NIMM directives, Hanus shell behavior, and mediation surface behavior.

Retained Hanus/AITAS/NIMM concept sources are summarized in [../../../docs/ontology/retained_cross_version_concepts.md](../../../docs/ontology/retained_cross_version_concepts.md).

Implemented for the MVP so far:

- minimal `aitas` attention and intention contracts
- minimal `nimm` directive normalization
- minimal `hanus_shell` action, state, reducer, and result contracts

Deferred in this phase:

- `mediation_surface` behavior
- tool attachment logic
- sandbox orchestration logic
- host or runtime composition logic
