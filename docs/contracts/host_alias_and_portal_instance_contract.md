# Host Alias And Portal Instance Contract

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This is the first authoritative V2 contract for hosted/network entities.

## Entity Set

### `portal_instance`

The deployed portal runtime identity.

Required fields:

- `portal_instance_id`
- `audience`
- `runtime_flavor`
- `domain`
- `deployment_state`

### `host_alias`

A named external or hosted-facing alias that projects from a `portal_instance`.

Required fields:

- `host_alias_id`
- `portal_instance_id`
- `alias_kind`
- `projection_state`
- `provider_truth_source`

### `progeny_link`

A declared relationship between one portal instance and another portal-facing
child, sibling, or derived network member.

Required fields:

- `progeny_link_id`
- `source_portal_instance_id`
- `target_portal_instance_id`
- `relationship_kind`
- `contract_state`

### `p2p_contract`

The authority object for portal-to-portal relationship rules.

Required fields:

- `p2p_contract_id`
- `authority_scope`
- `relationship_kind`
- `evidence_state`
- `enforcement_state`

### `external_service_binding`

A provider-binding declaration used by a tool or host alias without granting
provider truth ownership to the tool itself.

Required fields:

- `binding_id`
- `binding_family`
- `subject_id`
- `provider_kind`
- `binding_state`

## Boundary Rules

- `portal_instance` owns runtime identity, not provider truth.
- `host_alias` projects hosted/network presence, not shell authority.
- `progeny_link` expresses relationship topology, not runtime routing.
- `p2p_contract` owns portal-to-portal authority.
- `external_service_binding` records service attachment, not P2P authority.

## Immediate implementation sequence

1. land these entity contracts in docs and runtime copy
2. map `/portal/network` tabs to these entities
3. add read-only network summaries
4. only then consider `host_alias_tool` runtime implementation

Status on April 13, 2026:

- steps `1` through `3` are implemented through the V2 `NETWORK` read model
- step `4` remains pending by design
