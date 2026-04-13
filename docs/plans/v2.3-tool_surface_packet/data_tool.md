# Data Tool

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Packet role: `held-out legacy-isolation doc`\
Queue posture: `outside the narrowed near-term set`

Disposition: `legacy_isolation`  
V2 tool id target: `data_tool`  
Config gate target: `tool_exposure.data_tool`  
Audience: none approved

## Current code, docs, and live presence

- Current code: no V2 `data_tool` registry entry or runtime entrypoint exists.
- Legacy evidence: V1 portal surface exists as a separate tool/workbench shape.
- Live presence: no separate live V2 tool presence was found during this audit.

## Reusable evidence vs legacy baggage

- Reusable evidence: the need for datum and document inspection survived, but it
  now belongs to the admin datum workbench and datum-recognition path.
- Legacy baggage: treating data inspection as a separate generic tool instead of
  a shell-owned datum surface.

## Required V2 owner layers and dependencies

- No standalone V2 `data_tool` is approved.
- Useful behavior should land in the existing datum/admin system surfaces and
  related contracts.
- No future runtime entrypoint or shell descriptor should be created under this
  name unless a new decision explicitly overturns this plan.

## Admin activity-bar behavior

- Remains absent from the activity bar.
- If a reserved `tool_exposure.data_tool` key appears, it should stay disabled
  and unused.

## Carry-forward and do-not-carry-forward

- Carry forward only datum-inspection needs through the datum workbench path.
- Do not recreate `data_tool` as a parallel tool shell or legacy workbench.
