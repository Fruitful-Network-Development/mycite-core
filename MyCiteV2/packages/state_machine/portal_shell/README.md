# Portal Shell

Authority: [../../../../docs/plans/v2-authority_stack.md](../../../../docs/plans/v2-authority_stack.md)

`packages/state_machine/portal_shell/` owns the shared shell contracts for the
single V2 portal shell:

- serialized shell action
- serialized shell state
- pure shell reducer
- normalized shell result
- one portal shell request and selection model
- one surface catalog rooted in `SYSTEM`, `NETWORK`, and `UTILITIES`
- one tool registry for `SYSTEM` child tool surfaces

This package does not own:

- port calls
- adapter behavior
- runtime composition side effects
- external integration state
