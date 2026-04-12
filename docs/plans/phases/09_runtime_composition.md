# Phase 09: Runtime Composition

## purpose

Compose inward layers into runnable host shapes without giving hosts semantic ownership.

## source authorities

- [../v2-authority_stack.md](../v2-authority_stack.md)
- [../../decisions/decision_record_0007_hosts_compose_but_do_not_own_domain_logic.md](../../decisions/decision_record_0007_hosts_compose_but_do_not_own_domain_logic.md)
- [../version-migration/v1_audit_map.md](../version-migration/v1_audit_map.md)

## inputs

- ports
- adapters
- tools
- sandboxes

## outputs

- runtime composition under `instances/_shared/runtime/`
- composition tests

## prohibited shortcuts

- instance-led architecture
- host-owned shell semantics
- host-owned domain semantics

## required tests

- integration loop for runtime composition
- architecture boundary loop for host ownership

## completion gate

Hosts only compose inward layers and no runtime wrapper becomes a semantic owner.

## follow-on phase dependencies

- [10_integration_testing.md](10_integration_testing.md)
- [11_cleanup_and_v1_retirement_review.md](11_cleanup_and_v1_retirement_review.md)
