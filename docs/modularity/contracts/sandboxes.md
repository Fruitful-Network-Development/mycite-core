# Sandboxes

- Owns: system sandbox state, tool sandbox state, staging, mediation workspaces.
- Does not own: contract semantics, KeyPass policy, instance declaration logic.
- Reads: instance context, tool capability metadata, canonical state adapters.
- Writes: sandbox and staging state under the instance bubble.
- Depends on: `portal_core/shared`, `portal_core/shell`, `tools/_shared`.
- Depended on by: workbench routes, mediation surfaces, future tool backends.

