# Frozen Decisions For The Admin Band

Authority: [../../authority_stack.md](../../authority_stack.md)

This file records what remains deliberately frozen during the admin-first track.

## Active admin-first sequence

- The first stable admin operating band is `Admin Band 0 Internal Admin Replacement`.
- The first trusted-tenant tool-bearing target is `Admin Band 1 Trusted-Tenant AWS Read-Only`.
- The first narrow write candidate is `Admin Band 2 Trusted-Tenant AWS Narrow Write`.

## Frozen decisions

- The admin shell entry comes before any tool-bearing slice.
- The admin runtime envelope comes before any trusted-tenant admin exposure.
- The admin home/status surface comes before the tool registry/launcher surface.
- The tool registry/launcher surface comes before AWS.
- AWS comes before Maps.
- Maps comes before AGRO-ERP.
- `newsletter-admin` stays retired as a standalone admin surface.
- No PayPal, analytics, keycloak, progeny workbench, or sandbox surface may displace AWS in the admin-first path.
- No tool may bypass the shell-owned registry/launcher.
- No tool may define shell legality.
- No direct provider-admin route may be treated as the v2 entry surface.
- No flavor-specific runtime expansion is part of the admin-first band.

## Internal-only rule

Until `Admin Band 0` is stable:

- all admin-first slices remain internal-only
- the tool registry must remain deny-by-default
- AWS may be planned, but not trusted-tenant exposed

## Questions intentionally frozen

- whether the admin home/status surface and the tool registry remain distinct views or later become one shell payload
- the exact future port and adapter names for AWS read-only and AWS narrow write seams
- whether PayPal or keycloak follows AGRO-ERP or remains a later independent track
