# Shell

- Owns: navigation verbs, inspector cards, tool capability normalization,
  activity link composition, shell-level activation rules.
- Does not own: tool state persistence, data-engine storage, vault policy.
- Reads: selected context, config context, tool capability metadata.
- Writes: shell payloads only.
- Depends on: `portal_core/shared`.
- Depended on by: tool runtime, service-tool mediation, workbench routes.

