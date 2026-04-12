# Operations

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `legacy_isolation`  
V2 tool id target: `operations`  
Config gate target: `tool_exposure.operations`  
Audience: none approved

## Current code, docs, and live presence

- Current code: no V2 `operations` tool exists.
- Legacy evidence: V1 package and portal surface exist.
- Live presence: no dedicated V2 admin-shell presence or state root was
  confirmed during this audit.

## Reusable evidence vs legacy baggage

- Reusable evidence: generic operator visibility needs survive, but the current
  V2 portal already has home/status, audit activity, and operational status
  surfaces for that role.
- Legacy baggage: broad workspace semantics and generic board/operations UI.

## Required V2 owner layers and dependencies

- No standalone `operations` tool is approved.
- Useful operator visibility should keep landing in shell-owned home/status,
  audit, or future narrow slices instead of a generic operations tool.

## Admin activity-bar behavior

- Remains absent from the activity bar.
- Any reserved `tool_exposure.operations` key should stay disabled and unused.

## Carry-forward and do-not-carry-forward

- Keep `operations` as legacy evidence only.
- Do not recreate it as a broad, catch-all V2 admin tool.
