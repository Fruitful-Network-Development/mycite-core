# MVP Out Of Scope

Authority: [v2-authority_stack.md](v2-authority_stack.md)

Everything in this file is explicitly deferred from the MVP.

## Deferred package areas

- `packages/modules/domains/*`
- `packages/modules/cross_domain/external_events`
- `packages/tools/*`
- `packages/sandboxes/*`
- `packages/adapters/event_transport`
- `packages/adapters/session_vault`
- `packages/adapters/portal_runtime`
- `packages/ports/datum_store`
- `packages/ports/payload_store`
- `packages/ports/event_log`
- `packages/ports/resource_resolution`
- `packages/ports/session_keys`
- `packages/ports/time_projection`
- `packages/ports/shell_surface`
- `packages/core/identities`
- `packages/core/structures/*`
- `packages/core/mss`
- `packages/core/crypto`
- `packages/state_machine/mediation_surface`

## Deferred behaviors

- tools of any kind
- sandboxes of any kind
- publication behavior
- contracts behavior
- reference-exchange behavior
- externally-meaningful event behavior
- HOPS and time-projection behavior
- SAMRAS structural behavior
- hosted behavior
- progeny behavior
- multi-flavor runtime behavior
- browser UI breadth
- advanced mediation surfaces

## Deferred test loops

- tool loop
- sandbox loop
- broad system integration
- multiple-adapter interoperability

## Freeze rule

If a future implementation step tries to pull any deferred area into MVP for convenience rather than necessity, it must stop and update the MVP boundary docs first.
