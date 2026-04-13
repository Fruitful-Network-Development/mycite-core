# Admin Network Root Read Model

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This contract defines the current V2 `NETWORK` root as a contract-first,
read-only entity model.

## Live surface

- route: `/portal/network`
- shell slice: `admin_band0.network_root`
- surface schema: `mycite.v2.admin.network_root.surface.v1`
- workbench kind: `network_root`
- inspector kind: `network_summary`

## Current runtime sources

The live runtime reads from the deployed instance state, not from provider
tool runtimes:

- `private/config.json`
- `private/network/hosted.json`
- `private/network/aliases/**`
- `private/network/progeny/**`
- `private/contracts/**`
- `private/network/request_log/*.ndjson`
- local admin audit file when configured

## Current entity summaries

`NETWORK` now summarizes these entity families directly:

- `portal_instance`
- `host_alias`
- `progeny_link`
- `p2p_contract`
- `external_service_binding`

These appear through the root tabs:

- `messages`: request-log evidence, counterparties, recent events
- `hosted`: portal instance, host aliases, external service bindings
- `profile`: alias/progeny projection and hosted tab declarations
- `contracts`: P2P contracts, progeny links, request-log evidence, local audit

## Boundary rules

- This surface is read-only.
- It does not launch `host_alias_tool` runtime behavior.
- It does not treat provider configuration as relationship authority.
- It does not collapse request-log evidence and local audit into one source of
  truth.

## Follow-on rule

The next hosted/network implementation step is still `host_alias_tool`
planning on top of this read model, not a shortcut back to
`tenant_progeny_profiles`.
