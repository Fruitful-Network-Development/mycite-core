# Analytics

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Family root: [FND-EBI](fnd_ebi.md)\
Packet role: `subordinate capability direction`

Disposition: `subordinate_capability`\
V2 tool id target: `analytics`  
Config gate target: `tool_exposure.analytics`  
Audience: `internal-admin` first if reopened

## Current packet role

`analytics` is not an approved standalone family root in the narrowed V2.3
packet.

It is a child capability direction under `FND-EBI`, which already owns the
profile-led service/site operational visibility family.

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

- Keep analytics inside `FND-EBI` as a child capability direction unless a
  future family brief explicitly says otherwise.
- Do not recreate the old mixed analytics dashboard as a standalone admin root
  surface.
