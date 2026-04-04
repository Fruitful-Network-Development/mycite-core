# Data Engine

- Owns: anthology loading, resource/reference registries, normalization,
  compilers, closures, migrations.
- Does not own: portal shell, tool UI, request routing.
- Reads: `data/anthology.json`, `data/resources/rc.*`, `data/references/rf.*`,
  cache under `RC/` and `RF/`.
- Writes: canonical data-engine artifacts only.
- Depends on: `mycite_core/runtime_host` for path helpers when needed.
- Depended on by: contracts, sandboxes, flavor routes, materializers.
