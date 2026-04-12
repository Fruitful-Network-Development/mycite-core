# Legacy Admin

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `legacy_isolation`  
V2 tool id target: `legacy_admin`  
Config gate target: `tool_exposure.legacy_admin`  
Audience: none approved

## Current code, docs, and live presence

- Current code: no V2 `legacy_admin` tool exists.
- Legacy evidence: V1 portal surface exists only as historical implementation
  detail.
- Live presence: no live V2 presence was found during this audit.

## Reusable evidence vs legacy baggage

- Reusable evidence: none that justifies a dedicated V2 tool.
- Legacy baggage: catch-all admin overflow surface that conflicts with the
  shell-owned V2 admin model.

## Required V2 owner layers and dependencies

- No V2 owner, port, adapter, or runtime entrypoint should be created under this
  name.
- If a future requirement appears, it must be re-specified as a real slice under
  a new, semantically narrow tool name.

## Admin activity-bar behavior

- Must remain absent from the activity bar.
- `tool_exposure.legacy_admin` should remain omitted or false.

## Carry-forward and do-not-carry-forward

- Keep `legacy_admin` isolated as historical evidence only.
- Do not use it as a dumping ground for unresolved future admin work.
