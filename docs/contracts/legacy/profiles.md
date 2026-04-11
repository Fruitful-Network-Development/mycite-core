# Profiles

- Owns: `config.json`, `msn.<msn_id>.json`, `fnd.<msn_id>.json`, derived profile
  context, public/private profile resolution.
- Does not own: tool runtime registration, contract storage, sandbox staging.
- Reads: app/private/public instance profile files and derived context.
- Writes: normalized profile payloads and materialized profile outputs.
- Depends on: `mycite_core/runtime_host`, `mycite_core/mss_resolution`.
- Depended on by: composition, shell, sandboxes, tools.
