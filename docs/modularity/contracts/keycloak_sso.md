# Keycloak SSO Tool

- Owns: Keycloak/tool-specific backend-ui contracts and auth-related tool state
  adapters.
- Does not own: container/runtime topology or portal-global shell behavior.
- Reads: instance-scoped auth/operations tool state under
  `private/utilities/tools/keycloak-sso/`.
- Writes: only auth-tool scoped state.
- Depends on: `tools/_shared`, `portal_core/shared`.
- Depended on by: operations and provisioning surfaces.

