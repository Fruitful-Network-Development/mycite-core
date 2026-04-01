# Tools Shared

- Owns: shared tool catalog, tool runtime helpers, tool spec loading, generic
  tool state-root helpers.
- Does not own: individual tool workflows, shell verb definitions, flavor
  routing.
- Reads: tool configuration from `config.json`, tool spec files, instance
  `private/utilities/tools/...`.
- Writes: no tool business data directly; may create canonical tool root
  directories.
- Depends on: `portal_core/shell`, `portal_core/shared`.
- Depended on by: all standalone tool modules and legacy wrapper seams.

