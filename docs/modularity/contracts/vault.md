# Vault

- Owns: KeyPass paths, vault adapters, scopes, policies, inventory handling.
- Does not own: generic utilities dumping ground behavior, unrelated tool state.
- Reads: instance-scoped vault state under `private/utilities/vault/` and future
  `vault/keypass/` adapters.
- Writes: KeyPass database, inventory, vault keys/contracts only.
- Depends on: `portal_core/shared`.
- Depended on by: shell views, contract handshakes, tool flows that require
  secrets.

