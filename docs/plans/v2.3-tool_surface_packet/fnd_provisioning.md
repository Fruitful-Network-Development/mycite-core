# FND Provisioning

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `defer`  
V2 tool id target: `fnd_provisioning`  
Config gate target: `tool_exposure.fnd_provisioning`  
Audience: `internal-admin` first if ever reopened

## Current code, docs, and live presence

- Current code: no V2 `fnd_provisioning` tool exists.
- Legacy evidence: V1 portal tool surface exists, but no current V2 module or
  runtime plan owns it.
- Live presence: no dedicated live utility or sandbox root was confirmed during
  this audit.

## Reusable evidence vs legacy baggage

- Reusable evidence: tenant/bootstrap provisioning needs may still exist as an
  operator workflow.
- Legacy baggage: route-local provisioning flows and mixed admin/runtime logic.

## Required V2 owner layers and dependencies

- A future V2 version would need one explicit provisioning semantic owner and a
  bounded admin-only write slice.
- Ports and adapters must be specified from the real provisioning authority, not
  guessed from legacy route behavior.
- No runtime entrypoint is approved until that domain authority exists.

## Admin activity-bar behavior

- Hidden and blocked by default.
- No activity-bar item until a provisioning slice exists and passes the
  writable-slice gate.

## Carry-forward and do-not-carry-forward

- Defer until the underlying provisioning domain is re-specified.
- Do not recreate legacy provisioning routes or treat this as a convenience
  catch-all admin tool.
