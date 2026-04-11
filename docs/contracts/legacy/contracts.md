# Contracts

- Owns: schemas, bindings, inheritance, reference validation, contract
  handshakes, receipts.
- Does not own: local sandbox authoring state, shell UI decisions, vault secret
  storage.
- Reads: contract JSON, bound references, inherited references, canonical data
  engine records.
- Writes: contract-store records and contract-related receipts only.
- Depends on: `mycite_core/mss_resolution`, `mycite_core/runtime_host`.
- Depended on by: shell mediation, sandboxes, tool modules that consume
  contract-managed references.
