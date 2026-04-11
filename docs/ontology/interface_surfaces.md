# Interface Surfaces

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

## Surface terms

- `shell surface`: the serialized state and legality surface owned by `packages/state_machine/`.
- `mediation surface`: state-machine projection rules for how a subject is viewed or acted on.
- `service seam`: a named capability boundary expressed through a port, not an excuse for a broad package bucket.
- `port interface`: an inward-facing contract that external implementations satisfy.
- `adapter`: an outward-facing implementation of a port.
- `sandbox boundary`: an orchestration boundary for staged work, not a domain owner.

## Non-equivalences

These terms must not be conflated:

- UI widget is not shell surface.
- Domain API is not runtime route.
- Tool capability is not shell ownership.
- Service seam is not a generic `services/` folder.
- Mediation surface is not a core utility bucket.
- Sandbox boundary is not a domain module.

## Tool attachment rules

- Tools attach to shell-defined context, attention, directive, and mediation surfaces.
- Tools may consume shell context and expose capabilities.
- Tools may not define alternate shell state.
- Tool runtime routes, when they exist later, are adapter or host composition concerns.

## Sandboxes

- Sandboxes mediate staged interactions between shell state, ports, adapters, and derived artifacts.
- Sandboxes do not decide domain truth.
- Sandboxes do not redefine datum authority.
