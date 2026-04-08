# V1 Retention Vs Recreation

Authority: [../authority_stack.md](../authority_stack.md)

## Recreate from scratch

- `mycite_core/state_machine/*`
- `mycite_core/reference_exchange/*`
- `mycite_core/publication/*`
- tool capability declarations and tool attachment surfaces

## Split apart before recreation

- `mycite_core/contract_line/*`
- `mycite_core/vault_session/*`
- `instances/_shared/portal/*`
- runtime path helpers spread across reusable code

## Retain as concept only

- Hanus attention/intention model from `../../../../docs/plans/hanus_interface_model.md`
- HOPS and chronology concepts from `../../../../docs/wiki/hops/homogeneous_ordinal_partition_structure.md`
- tool authority rules from `../../../../docs/plans/tool_dev.md`

## Historical evidence only

- `packages/hosts/server_portal/`
- instance-led placeholder layouts
- v1 wrapper reexports such as `mycite_core/runtime_paths.py`

## Discard

- broad `services` naming as an ontology bucket
- direct host/runtime imports inside reusable logic
- utility JSON treated as datum truth
- copied v1 package shapes with only cosmetic renaming
