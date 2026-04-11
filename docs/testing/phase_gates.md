# Phase Gates

Authority: [../plans/authority_stack.md](../plans/authority_stack.md)

Phase completion is defined jointly by this file and [../plans/phase_completion_definition.md](../plans/phase_completion_definition.md).

## Gate rules

- A phase is complete only when its declared outputs exist.
- Required tests for that phase must pass at the correct boundary loop.
- No prohibited shortcut from that phase may remain in tree.
- Later-layer code must not be used to compensate for missing earlier-layer definitions.
- All authoritative docs touched by the phase must still align with [../plans/authority_stack.md](../plans/authority_stack.md).
