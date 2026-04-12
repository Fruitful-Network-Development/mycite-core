# Progressive Solidification

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

Implementation in v2 proceeds by ordered solidification. Order matters because later layers depend on earlier meaning.

## Ordered phases

1. Ontology and structure
2. Core pure modules
3. State machine and Hanus shell
4. Ports
5. Domain and cross-domain modules
6. Adapters
7. Tools
8. Sandboxes
9. Runtime composition
10. Integration testing
11. Cleanup and v1 retirement review

## Rules

- A later phase may not define missing meaning for an earlier phase.
- A phase is incomplete until its completion gate passes. See [../plans/v2-phase_completion_definition.md](../plans/v2-phase_completion_definition.md).
- Each phase must use the fixed section schema defined in [../plans/phases/](../plans/phases/).
- Scaffold-phase work is inert by design. See [../plans/v2-implementation_prohibition_for_scaffold_phase.md](../plans/v2-implementation_prohibition_for_scaffold_phase.md).
