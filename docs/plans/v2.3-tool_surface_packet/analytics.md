# Analytics

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `defer`  
V2 tool id target: `analytics`  
Config gate target: `tool_exposure.analytics`  
Audience: `internal-admin` first if reopened

## Current code, docs, and live presence

- Current code: no V2 `analytics` tool exists.
- Legacy evidence: V1 analytics package and docs still exist.
- Live presence: the V2 health surface still reports analytics roots for FND and
  TFF, but there is no separate analytics tool in the live admin shell.

## Reusable evidence vs legacy baggage

- Reusable evidence: website/member analytics storage and reporting needs.
- Legacy baggage: standalone analytics tool UI, legacy routes, and mixed portal
  dashboard behavior.

## Required V2 owner layers and dependencies

- A future V2 version needs one narrow analytics semantic owner and explicit
  read-only ports for reporting data.
- It should reuse the current health/analytics root knowledge instead of
  reviving V1 runtime shapes.
- No runtime entrypoint or shell descriptor is approved yet.

## Admin activity-bar behavior

- Hidden and blocked by default.
- No activity-bar item until a read-only analytics slice is explicitly approved
  after the current priority sequence.

## Carry-forward and do-not-carry-forward

- Defer analytics until after the current admin/tool gating work.
- Do not recreate the old mixed analytics dashboard as a default admin shell
  surface.
