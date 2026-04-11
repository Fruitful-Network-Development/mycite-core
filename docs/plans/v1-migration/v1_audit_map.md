# V1 Audit Map

Authority: [../authority_stack.md](../authority_stack.md)

This map is conceptual relocation guidance, not a copy plan.

## `mycite_core/state_machine/*`

- V1 role: shell/state owner with Hanus, AITAS, NIMM, and tool capability logic
- V2 destination: `packages/state_machine/`
- V1 issue: mixed imports from `instances._shared.portal.data_engine`

## `mycite_core/datum_refs.py`, `mycite_core/mss_resolution/*`

- V1 role: pure-ish structural utilities
- V2 destination: `packages/core/datum_refs/` and `packages/core/mss/`
- V1 issue: runtime helpers still leak into nearby code

## `mycite_core/reference_exchange/*`

- V1 role: domain concern
- V2 destination: `packages/modules/domains/reference_exchange/`
- V1 issue: imports portal data-engine resource code directly

## `mycite_core/publication/*`

- V1 role: domain concern
- V2 destination: `packages/modules/domains/publication/`
- V1 issue: split between domain logic and profile/runtime path handling is unclear

## `mycite_core/contract_line/*`

- V1 role: domain-adjacent contract handling
- V2 destination: `packages/modules/domains/contracts/`
- V1 issue: imports sandbox and portal services directly

## `mycite_core/external_events/*`

- V1 role: cross-domain event substrate
- V2 destination: `packages/modules/cross_domain/external_events/`
- V1 issue: coupled to runtime path helpers

## `mycite_core/local_audit/*`

- V1 role: cross-domain audit substrate
- V2 destination: `packages/modules/cross_domain/local_audit/`
- V1 issue: treated like generic service or helper rather than narrow cross-domain owner

## `mycite_core/vault_session/*`

- V1 role: mixed crypto, key storage, and session behavior
- V2 destination: split across `packages/core/crypto/`, `packages/ports/session_keys/`, and `packages/adapters/session_vault/`
- V1 issue: one name hides multiple ontological categories

## `packages/tools/*`

- V1 role: canonical tool code
- V2 destination: `packages/tools/*`
- V1 issue: must stay shell-attached rather than drifting toward host-owned logic

## `packages/hosts/*` and `instances/_shared/runtime/*`

- V1 role: runtime composition
- V2 destination: `instances/_shared/runtime/`
- V1 issue: historical host ownership blurred with semantics

## `instances/_shared/portal/*`

- V1 role: mixed shared core, routes, portal services, data engine, mediation, sandbox, and shell wrappers
- V2 destination: split across `core`, `state_machine`, `modules`, `ports`, `adapters`, `sandboxes`, and runtime composition
- V1 issue: this tree is the main evidence of mixed concern ownership
