# Composition

- Owns: runtime flavor loading, instance loading, instance-context creation,
  binding instance declarations to runtime state roots.
- Does not own: Flask route behavior, tool-specific workflows, direct data
  engine mutation.
- Reads: environment, instance declarations, canonical state-root helpers.
- Writes: derived instance context objects only.
- Depends on: `mycite_core/runtime_host`, `instances/declarations`.
- Depended on by: `runtime/`, flavor apps, materializers.
