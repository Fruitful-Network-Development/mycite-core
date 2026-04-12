# Keycloak SSO

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `defer`  
V2 tool id target: `keycloak_sso`  
Config gate target: `tool_exposure.keycloak_sso`  
Audience: `internal-admin` first if reopened

## Current code, docs, and live presence

- Current code: no V2 `keycloak_sso` tool exists.
- Legacy evidence: V1 tool package, docs, and FND utility roots still exist.
- Live presence: FND still has `private/utilities/tools/keycloak-sso/`; no live
  V2 admin-shell entry exists.

## Reusable evidence vs legacy baggage

- Reusable evidence: auth-provider operator state and instance-level config
  files.
- Legacy baggage: V1 provider-admin assumptions and route-local auth operations.

## Required V2 owner layers and dependencies

- Any V2 tool would need one explicit auth-operations owner and a new operator
  boundary review against current portal auth rules.
- Ports and adapters must be scoped to auth-provider state only.
- No runtime entrypoint is approved before that boundary review.

## Admin activity-bar behavior

- Hidden and blocked by default.
- No activity-bar item until auth/provider operations are explicitly approved as
  a V2 admin slice family.

## Carry-forward and do-not-carry-forward

- Defer until auth-provider operations become an approved follow-on area.
- Do not import legacy provider-admin route patterns or config-driven mounting.
