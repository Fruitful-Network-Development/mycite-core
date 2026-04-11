# V2 Surface Ownership Map

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This file states what each major V2 surface owns so the repo stays modular and
does not slide back into V1-style boundary blur.

## Surface map

| Surface | Owns | Must not own |
| --- | --- | --- |
| `docs/` | V2 semantics, ontology, decisions, plans, and completion records | runtime transport, host wiring, or live-state mutations |
| `MyCiteV2/instances/_shared/portal_host/` | HTTP transport, shell asset serving, host health surface, and request-to-runtime wiring | domain rules, shell legality, or direct filesystem semantics |
| `MyCiteV2/instances/_shared/runtime/` | runtime entrypoint composition, runtime envelopes, and approved launch surfaces | HTTP hosting, nginx behavior, or direct live-state persistence details |
| `MyCiteV2/packages/state_machine/` | shell state, reducer behavior, launch legality, and state-machine contracts | filesystem IO, route mounting, or deployment topology |
| `MyCiteV2/packages/ports/` | boundary contracts for data, events, AWS, audit, session, and shell surfaces | concrete storage, host glue, or tool-specific UI transport |
| `MyCiteV2/packages/adapters/` | concrete implementations for approved ports, portal/runtime transport adapters, and filesystem mapping | domain ownership, shell policy, or architecture precedence |
| `MyCiteV2/packages/modules/` | domain and cross-domain use cases built on inward contracts | host transport, repo authority, or outward dependency shortcuts |
| `MyCiteV2/packages/core/` | pure types, refs, identities, and low-level structural primitives | runtime orchestration, adapter behavior, or host concerns |
| `MyCiteV2/packages/sandboxes/` | staging, orchestration, and mediated execution boundaries | canonical domain truth or production host policy |
| `MyCiteV2/tests/` | verification by unit, contract, integration, and architecture boundary loop | replacing contracts, ontology, or plans as authority |
| `MyCiteV1/` | migration evidence, historical implementation detail, and retirement-review scope | defining new V2 structure or current live modular ownership |

## Reading rule

When a question is about purpose or ownership, resolve it here before using
path names or older implementations as evidence.

## Promotion rule

Promote content into current non-legacy docs only when it applies to the
surface owners above without dragging V1 package shape or deployment history
forward.
