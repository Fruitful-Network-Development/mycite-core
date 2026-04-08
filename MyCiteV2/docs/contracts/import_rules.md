# Import Rules

Authority: [../plans/authority_stack.md](../plans/authority_stack.md)

## Allowed directions

- `packages/core` imports only itself and standard library.
- `packages/state_machine` imports `packages/core`.
- `packages/modules/domains` and `packages/modules/cross_domain` import inward layers only.
- `packages/ports` import inward layers and declare interfaces only.
- `packages/adapters` implement ports and may import inward layers.
- `packages/tools` import shell, ports, and inward layers without owning shell truth.
- `packages/sandboxes` import shell, ports, and inward layers for orchestration only.
- `instances/_shared/runtime` composes all inward layers without redefining them.

## Forbidden patterns

- Any import from `instances/` outside runtime composition.
- Any import from `packages/adapters/` into `core`, `state_machine`, `modules`, or `ports`.
- Any hardcoded live-state path import or runtime path helper inside inward layers.
- Any tool import into `state_machine` that makes tool code define shell legality.
- Any sandbox import into domain modules that makes sandbox code define domain semantics.

## Checks to enforce later

- Layer-order import scan
- Forbidden-path string scan
- Instance-id and instance-path string scan
- Live-state root scan
- Host-wrapper import scan

See [../testing/architecture_boundary_checks.md](../testing/architecture_boundary_checks.md).
