# Contracts

- Owns: schemas, bindings, inheritance, reference validation, contract
  handshakes, receipts.
- Does not own: local sandbox authoring state, shell UI decisions, vault secret
  storage.
- Reads: contract JSON, bound references, inherited references, canonical data
  engine records.
- Writes: contract-store records and contract-related receipts only.
- Depends on: `portal_core/data_engine`, `portal_core/shared`.
- Depended on by: shell mediation, sandboxes, tool modules that consume
  contract-managed references.

