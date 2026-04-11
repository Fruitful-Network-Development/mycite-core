# Phase 10: Integration Testing

## purpose

Validate cross-layer behavior only after inward layers, ports, adapters, tools, sandboxes, and runtime composition are stable.

## source authorities

- [../authority_stack.md](../authority_stack.md)
- [../../testing/testing_philosophy.md](../../testing/testing_philosophy.md)
- [../../testing/architecture_boundary_checks.md](../../testing/architecture_boundary_checks.md)

## inputs

- completed phases 02 through 09

## outputs

- integration suites
- architecture enforcement suites

## prohibited shortcuts

- using integration tests to excuse missing lower-layer coverage
- weakening boundary checks to pass composition tests

## required tests

- integration loop
- architecture boundary loop

## completion gate

Cross-layer behavior passes without hiding broken boundary ownership underneath.

## follow-on phase dependencies

- [11_cleanup_and_v1_retirement_review.md](11_cleanup_and_v1_retirement_review.md)
