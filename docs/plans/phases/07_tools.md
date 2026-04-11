# Phase 07: Tools

## purpose

Recreate tool packages as shell-attached capability owners rather than alternate shells or host extensions.

## source authorities

- [../authority_stack.md](../authority_stack.md)
- [../../ontology/interface_surfaces.md](../../ontology/interface_surfaces.md)
- [../../V1/plans/tool_dev.md](../../V1/plans/tool_dev.md)

## inputs

- state-machine surface contracts
- ports
- adapters as needed

## outputs

- `packages/tools/*`
- tool capability declarations
- tool boundary tests

## prohibited shortcuts

- tool-owned shell state
- direct flavor imports
- utility JSON promoted to datum truth

## required tests

- tool loop
- contract loop for capability declarations
- architecture boundary loop

## completion gate

Tools consume shell context through defined surfaces and do not redefine shell legality or datum authority.

## follow-on phase dependencies

- [08_sandboxes.md](08_sandboxes.md)
- [09_runtime_composition.md](09_runtime_composition.md)
