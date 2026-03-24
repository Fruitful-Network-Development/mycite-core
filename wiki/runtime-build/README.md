# Runtime And Build

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md)

## Status

Canonical topic

## Current Contract

Runtime semantics are shared-core owned and file-backed. `build.json` remains a bootstrap materialization input rather than a live runtime authority.

## Host infrastructure (srv-infra)

Host-level concerns—NGINX vhosts, `compose/portals` stack, `compose/platform` (Keycloak, oauth2-proxy, DB)—live in the **`srv-infra`** repository, separate from `mycite-core`. The historical `compose/platform/flask-bff` “BFF” directory was removed as dead weight; it is not part of the current portal deployment model.

## Pages

- [Shared Core And Flavor Boundaries](shared-core-and-flavor-boundaries.md)
- [Build And Materialization](build-and-materialization.md)
- [Portal Config Model](portal-config-model.md)

## Source Docs

- `docs/PORTAL_CORE_ARCHITECTURE.md`
- `docs/PORTAL_BUILD_SPEC.md`
- `docs/PORTAL_UNIFIED_MODEL.md`
- `docs/COMPOSE_FILE_TREE.md`

## Update Triggers

- Changes to shared-core or flavor ownership
- Changes to materialization authority
- Changes to runtime config canonicalization
- Changes to live-state boundary rules
