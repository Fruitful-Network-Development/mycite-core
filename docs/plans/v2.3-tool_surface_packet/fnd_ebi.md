# FND-EBI

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `carry_forward`  
V2 tool id target: `fnd_ebi`  
Config gate target: `tool_exposure.fnd_ebi`  
Audience: `internal-admin` first, trusted-tenant later if approved

## Current code, docs, and live presence

- Current code: no V2 `fnd_ebi` registry entry or runtime entrypoint exists.
- Legacy evidence: V1 service-tool mediation docs, tests, and utility-state
  files still exist.
- Live presence: FND still has `private/utilities/tools/fnd-ebi/` and
  `data/sandbox/fnd-ebi/sources/`; TFF does not.

## Reusable evidence vs legacy baggage

- Reusable evidence: service-profile files, analytics/site-root state, and
  source-backed registrar data.
- Legacy baggage: config-driven portal exposure, tool-layer mediation, and V1
  runtime glue.

## Required V2 owner layers and dependencies

- Shell registry: a future `fnd_ebi` descriptor if and only if the tool is
  explicitly approved as a V2 admin slice.
- Runtime entrypoint: one read-only admin entrypoint first.
- Semantic owner: one narrow service/analytics visibility module, not a revived
  legacy tool package.
- Port and adapter: profile-read seam for `private/utilities/tools/fnd-ebi/`
  plus any explicit datum read seam needed for sandbox sources.

## Admin activity-bar behavior

- Hidden and blocked unless `tool_exposure.fnd_ebi.enabled=true`.
- No activity-bar item until a V2 slice exists.
- Trusted-tenant exposure is a later decision and is not part of this packet.

## Carry-forward and do-not-carry-forward

- Carry forward only the narrow service-integration visibility that fits V2
  shell-owned surfaces.
- Do not recreate V1 tool mediation or legacy config-driven mounting.
