# Data Engine

- Owns: anthology loading, datum identity, resource/reference registries, payload compilation/decoding, closures, and migrations.
- Does not own: portal shell composition, tool UI, or direct request routing.
- Reads: `data/anthology.json`, scoped local/inherited resource descriptors, and payload binaries/cache under `data/payloads/`.
- Writes: canonical data-engine artifacts only; derived binary/cache rewrites are allowed only in the payload materialization boundary.
- Binary authority: `data/payloads/*.bin` and `data/payloads/cache/*.json` are the only binary and decoded-payload roots.
- Compatibility posture: legacy root `data/resources` and `data/references` inputs may still be surfaced for migration/read compatibility, but they are not separate binary authority.
- Depends on: `mycite_core/runtime_host` path helpers when needed.
- Depended on by: contracts, sandboxes, flavor routes, and materializers.
