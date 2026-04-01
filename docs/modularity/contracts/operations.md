# Operations Tool

- Owns: operations-specific backend/ui/contracts and operations state adapter.
- Does not own: runtime supervisor config, container topology, unrelated tool
  state.
- Reads: instance-scoped operations data under
  `private/utilities/tools/keycloak-sso/`.
- Writes: operations-specific collections and action state only.
- Depends on: `tools/_shared`, `portal_core/shared`.
- Depended on by: provisioning/operations mediation surfaces.

