# V2 NETWORK V1 To V2 Crosswalk Audit

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

## Summary

- Current V2 `NETWORK` is a read-only, contract-first shell root.
- Current V2 `NETWORK` is not the old V1 contract editor or profile-write
  surface.
- Live runtime verification on April 14, 2026 shows the deployed root resolves
  as `active_service=network`, `workbench_kind=network_root`, and
  `summary.hosted_root=contract_first_read_model`.

## Live runtime proof

Tracked live shell verification against the deployed V2 portals returned:

- `requested_slice_id=admin_band0.network_root`
- `active_service=network`
- `workbench_kind=network_root`
- `summary.hosted_root=contract_first_read_model`

This confirms the live root is already aligned to the read-model contract and
is not falling back to legacy V1 `NETWORK` editor semantics.

## V1 To V2 Crosswalk

| V1 idea | V2 status | Current V2 truth |
| --- | --- | --- |
| `NETWORK` as the portal-to-portal shell root | carried forward | `/portal/network` remains the root shell entrypoint |
| request logs and counterpart evidence | carried forward | `messages` tab summarizes request-log evidence and counterpart flows |
| hosted views | carried forward | `hosted` tab summarizes `portal_instance`, `host_alias`, and `external_service_binding` |
| profile/progeny projection | narrowed and carried forward | `profile` tab is read-model projection only |
| contracts context | carried forward in narrowed form | `contracts` tab summarizes `p2p_contract`, `progeny_link`, request-log evidence, and local audit |
| `NETWORK > Contracts` as the canonical contract editor | retired from current V2 root | V2 summarizes contracts read-only; no editor is active on the shell root |
| profile editing from `NETWORK > Profile` | retired from current V2 root | V2 `NETWORK` does not own write APIs or datum-write intents |
| `tenant_progeny_profiles` placeholder | retired | follow-on hosted work starts from entity contracts and the read-only root, not the placeholder plan |
| `host_alias_tool` runtime loader | deferred | remains a later follow-on after the current entity contracts and read model |

## Retired Versus Active

Active in V2:

- root tabs for request evidence, hosted entities, projection, and contract
  summaries
- the entity set `portal_instance`, `host_alias`, `progeny_link`,
  `p2p_contract`, and `external_service_binding`
- local audit as a separate evidence source beside request logs

Retired from the current root:

- contract editing on `NETWORK`
- profile-write actions on `NETWORK`
- `tenant_progeny_profiles` as a shortcut around hosted/entity contracts
- any runtime implication that `host_alias_tool` is already implemented

## Operational Rule

Use the current V2 contracts as the forward authority:

- [../contracts/admin_network_root_read_model.md](../contracts/admin_network_root_read_model.md)
- [../contracts/network_operation_and_p2p_boundary.md](../contracts/network_operation_and_p2p_boundary.md)
- [../contracts/host_alias_and_portal_instance_contract.md](../contracts/host_alias_and_portal_instance_contract.md)

Keep legacy wiki pages intact as historical evidence only. They explain where
the model came from, but they do not override the current V2 read-only
contract.
