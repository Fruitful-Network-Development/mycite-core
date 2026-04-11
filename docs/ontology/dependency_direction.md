# Dependency Direction

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

## Direction

Dependency direction flows inward:

1. `packages/core/`
2. `packages/state_machine/`
3. `packages/modules/domains/` and `packages/modules/cross_domain/`
4. `packages/ports/`
5. `packages/adapters/`
6. `packages/tools/`
7. `packages/sandboxes/`
8. `instances/_shared/runtime/`

## Allowed import summary

- `core` may import only `core` and standard library.
- `state_machine` may import `core`.
- `modules/domains` may import `core` and stable types from `state_machine` only when those types are explicitly state-free.
- `modules/cross_domain` may import `core` and the same narrow shared types as domain modules.
- `ports` may import `core` plus domain and cross-domain contracts, never adapters.
- `adapters` may import ports and inward layers.
- `tools` may import `state_machine`, `ports`, and inward layers, but never define shell truth.
- `sandboxes` may import `state_machine`, `ports`, and inward layers for orchestration only.
- `instances/_shared/runtime` may import all inward layers for composition only.

## Forbidden import summary

- No inward layer may import `instances/`.
- No inward layer may import `adapters/`.
- `core` must not import `state_machine`, `modules`, `ports`, `adapters`, `tools`, `sandboxes`, or `instances`.
- `state_machine` must not import `tools`, `sandboxes`, `adapters`, or `instances`.
- `modules` must not import runtime wrappers, instance paths, or host code.
- `tools` must not own shell state or import flavor code.
- `sandboxes` must not absorb contract semantics, publication semantics, or reference-exchange semantics.

Details live in [../contracts/import_rules.md](../contracts/import_rules.md).
