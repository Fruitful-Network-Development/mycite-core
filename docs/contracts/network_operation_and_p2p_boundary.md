# Network Operation And P2P Boundary

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This contract defines the forward role of `/portal/network`.

## Root posture

- `/portal/network` is a shell root, not a tool family surface.
- It now exposes a contract-first read model over hosted/network entities.
- It is not the old V1 `NETWORK` contract-editor or profile-write surface.
- It must point to hosted/network entity contracts instead of provider
  placeholders.

## Root tabs

Current tab ownership:

- `messages`: request and message flows anchored between portal instances
- `hosted`: `portal_instance`, `host_alias`, and `external_service_binding`
  summaries
- `profile`: alias/profile projection only
- `contracts`: `p2p_contract`, `progeny_link`, request-log evidence, and local
  audit summaries

## Hard separations

- P2P authority is owned by `p2p_contract`.
- MSS or profile projection is a projection concern, not authority.
- request-log evidence is evidence, not a source of legality by itself.
- local audit remains local audit; it does not replace relationship contracts.

## Immediate implementation rule

- runtime copy and docs may summarize these areas now
- the read-only network root model is now live from deployed instance state
- no hosted or host-alias runtime loader lands before the entity contracts
- `tenant_progeny_profiles` does not reopen as a shortcut around this sequence
