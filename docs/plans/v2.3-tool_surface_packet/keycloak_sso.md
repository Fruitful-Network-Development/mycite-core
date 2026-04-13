# Keycloak SSO

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Canonical name: `Keycloak SSO`\
Packet role: `family_root`\
Queue posture: `typed family plan only`\
Primary future gate target: `tool_exposure.keycloak_sso`

## Completion intent

`Keycloak SSO` is the single identity-provider operations family for
Keycloak-backed sign-in and operator-facing SSO posture.

It should stay admin-first and read-only first.

It must not be treated as a convenience way to reintroduce legacy provider-admin
sprawl or route-local auth mutation.

## Current code, docs, and live presence

- Current code: no V2 `keycloak_sso` tool exists.
- Legacy evidence: V1 tool/package docs and FND utility roots still exist.
- Live presence: FND still has `private/utilities/tools/keycloak-sso/`; no live
  V2 admin-shell entry exists.

## Stable authority model

Any future V2 version should use one explicit auth-operations owner with ports
and adapters scoped to provider state only.

The first typed family posture should center on:

- provider/realm posture visibility
- client/application linkage visibility
- domain/redirect/readiness summaries
- bounded reconciliation or administrative actions only after explicit approval

## First completion sequence

### Slice 1 — read-only SSO/provider posture

Must provide:

- provider configuration visibility
- client/realm state summaries
- operator warnings and mismatch visibility

### Slice 2 — bounded reconciliation or maintenance actions

Later and only after an auth-boundary review approves explicit write semantics.

## Do not carry forward

Do not carry forward:

- legacy provider-admin route patterns
- config-driven mounting
- broad auth mutation surfaces by convenience
