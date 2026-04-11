# Testing Philosophy

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

V2 uses layered test loops so phase completion is checked at the same boundary where meaning lives.

## Test loops

- `pure unit loop`: validates deterministic logic in `packages/core`.
- `contract loop`: validates ports, module contracts, and schema-level expectations.
- `adapter loop`: validates adapter conformance to ports without redefining semantics.
- `tool loop`: validates tool capability declaration and shell attachment behavior.
- `sandbox loop`: validates orchestration rules, staging behavior, and derived-artifact boundaries.
- `integration loop`: validates composed behavior across multiple layers.
- `architecture boundary loop`: validates imports, naming, authority zones, and path assumptions.

## Rule

No phase may advance on integration tests alone. Each phase must pass the loop that matches its own semantic boundary first.
