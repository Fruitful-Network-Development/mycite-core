# One-Shell Behavioral Alignment Audit

Structural one-shell cleanup is complete.

This follow-up alignment pass corrected the remaining behavioral mismatch between:

- the structural one-shell inventory model
- the intended `SYSTEM` workspace and tool mediation behavior

Observed repository state after alignment:

- one shell request/state/composition family
- one runtime envelope model
- one reducer-owned `SYSTEM` workspace state model
- reducer ownership limited to `system.root` and `system.tools.*`
- `/portal/system/operational-status` kept as a plain read-model route under `SYSTEM`
- `activity` and `profile_basics` folded into `/portal/system` workspace file modes
- ordered focus stack implemented as `sandbox -> file -> datum -> object`
- explicit `back_out` contraction rules implemented
- interface panel made mediation-owned on `SYSTEM`
- tool pages made interface-panel-led by default with `regions.workbench.visible=false`
- runtime-owned canonical route/query projection returned for reducer-owned surfaces

The repository should now be described as:

> One portal shell, rooted in `SYSTEM` / `NETWORK` / `UTILITIES`, with a
> reducer-owned `SYSTEM` workspace model, interface-panel-led tool mediation,
> and route/query state projected from canonical runtime state.
