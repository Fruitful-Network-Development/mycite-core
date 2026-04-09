# Runtime Entrypoints

Authority: [../authority_stack.md](../authority_stack.md)

This file catalogs runtime entrypoints and constrains how new ones are added.

## Policy

- Runtime entrypoints live under `instances/_shared/runtime/`.
- A runtime entrypoint is a top-level callable meant for host or test composition.
- One approved slice gets one public runtime entrypoint.
- Helper functions stay private inside the same file unless a later slice proves a shared need.
- No flavor-specific runtime composition is allowed in the current operating band.
- Runtime entrypoints may compose inward layers, but they may not define shell semantics, domain semantics, port contracts, or adapter rules.

## Current catalog

| Entrypoint id | Callable | Slice | Band | Exposure status | Inputs | Outputs |
|---|---|---|---|---|---|---|
| `mvp.shell_action_to_local_audit` | `instances._shared.runtime.mvp_runtime.run_shell_action_to_local_audit` | `Shell Action To Local Audit` | Band 0 | internal-only | serialized shell action payload, caller-supplied audit storage file | normalized subject, normalized shell verb, normalized shell state, persisted audit identifier, persisted audit timestamp |

## Required catalog fields for future entrypoints

Every new entrypoint must be added here before implementation and must record:

- entrypoint id
- callable path
- slice id
- rollout band
- exposure status
- input contract
- output contract
- external configuration inputs
- owning tests

## Approval rule for new entrypoints

- A second public runtime entrypoint may not be added until its slice file exists in [slice_registry/](slice_registry/).
- A runtime entrypoint may not be added for an exposure band that is currently frozen.
- A runtime entrypoint may not be added just to compensate for missing lower-layer contracts.

## Forbidden runtime drift

- No tool wiring in shared runtime entrypoints during the current band.
- No sandbox orchestration in shared runtime entrypoints during the current band.
- No hidden read or write side channels.
- No instance-led directory math inside inward layers.
- No flavor copies of the same entrypoint.
