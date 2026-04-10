# Hanus Shell

Authority: [../../../docs/plans/authority_stack.md](../../../docs/plans/authority_stack.md)

`packages/state_machine/hanus_shell/` owns the MVP Hanus shell contracts:

- serialized shell action
- serialized shell state
- pure shell reducer
- normalized shell result
- serialized admin shell request and selection state for the internal admin band
- shell-owned admin slice catalog and tool-registry gating rules
- shell-owned admin tool launch decisions for the AWS read-only slice
- shell-owned admin tool launch decisions for the AWS narrow-write slice

This package does not own:

- port calls
- adapter behavior
- tool legality
- sandbox behavior
- runtime composition
