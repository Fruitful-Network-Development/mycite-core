# ADR 0010: Post-MVP Staging And Rollout Surface

## Status

Accepted

## Context

The MVP proves the architecture, but it does not yet define how the rest of the portal should be rolled out safely to clients. Without a post-MVP operating surface, future agents would likely widen scope, recreate v1 workflow drift, or let runtime composition become a new semantic owner.

## Decision

Post-MVP work must proceed through:

- explicit rollout bands
- a mandatory slice registry
- explicit client exposure gates
- a runtime entrypoint catalog
- a port and adapter ownership matrix
- frozen decisions for the current band
- reusable agent prompt templates

The controlling documents are:

- [../plans/post_mvp_rollout/portal_rollout_bands.md](../plans/post_mvp_rollout/portal_rollout_bands.md)
- [../plans/post_mvp_rollout/v1_parity_ledger.md](../plans/post_mvp_rollout/v1_parity_ledger.md)
- [../plans/post_mvp_rollout/client_exposure_gates.md](../plans/post_mvp_rollout/client_exposure_gates.md)
- [../plans/post_mvp_rollout/runtime_entrypoints.md](../plans/post_mvp_rollout/runtime_entrypoints.md)
- [../plans/post_mvp_rollout/port_adapter_ownership_matrix.md](../plans/post_mvp_rollout/port_adapter_ownership_matrix.md)
- [../plans/post_mvp_rollout/frozen_decisions_current_band.md](../plans/post_mvp_rollout/frozen_decisions_current_band.md)
- [../plans/post_mvp_rollout/agent_prompt_templates.md](../plans/post_mvp_rollout/agent_prompt_templates.md)

## Consequences

- Future prompts can be smaller because the slice file and rollout docs carry the missing context.
- Read-only client exposure is prioritized before writable exposure.
- Runtime entrypoints stay composition-only and cataloged.
- V1 parity becomes workflow-level prioritization evidence instead of structural pressure.
- Tools, sandboxes, flavor expansion, and broad admin flows stay outside the current band unless an explicit later decision changes that.
