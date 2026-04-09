# Hanus Shell

Authority: [../../../docs/plans/authority_stack.md](../../../docs/plans/authority_stack.md)

`packages/state_machine/hanus_shell/` owns the MVP Hanus shell contracts:

- serialized shell action
- serialized shell state
- pure shell reducer
- normalized shell result

This package does not own:

- port calls
- adapter behavior
- tool legality
- sandbox behavior
- runtime composition
