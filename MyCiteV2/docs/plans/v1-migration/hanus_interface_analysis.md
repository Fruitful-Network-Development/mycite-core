# Hanus Interface Analysis

Authority: [../authority_stack.md](../authority_stack.md)

This document synthesizes Hanus-facing lessons from:

- [../../../../docs/plans/hanus_interface_model.md](../../../../docs/plans/hanus_interface_model.md)
- [historical/1-Analysis.md](historical/1-Analysis.md)

## Core takeaways

- Hanus belongs to the serialized shell surface, not to host code and not to tool code.
- Attention and intention must remain explicit state-machine concepts.
- HOPS and SAMRAS are structure and address concerns. Projection belongs above them, not inside them.
- Mediation behavior must live with shell/state behavior, which is why v2 uses `packages/state_machine/mediation_surface/`.

## Implications for v2

- `packages/state_machine/hanus_shell/` owns Hanus-facing state contracts.
- `packages/state_machine/aitas/` owns context vocabulary, not runtime wrappers.
- `packages/ports/time_projection/` exists because HOPS/time projection is a seam, not an ad hoc helper.
- Tools may consume Hanus state but must not redefine it.
