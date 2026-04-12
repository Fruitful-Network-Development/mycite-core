# AWS-CSM Sandbox

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `current_v2`  
V2 tool id: `aws_csm_sandbox`  
Config gate target: `tool_exposure.aws_csm_sandbox`  
Audience: `internal-admin`

## Current code, docs, and live presence

- Current code: `admin_band3.aws_csm_sandbox_surface`,
  `admin.aws.csm_sandbox_read_only`, and the shell-owned registry entry already
  exist.
- Live presence: FND and TFF both report the tool in live admin-shell output.
- Current docs: `T-007` remains the key investigation record for why this tool
  is separate from production AWS read-only.

## Reusable evidence vs legacy baggage

- Reusable evidence: separate sandbox profile root, internal-only launch rule,
  and read-only staging posture.
- Legacy baggage: broad sandbox/session sprawl and V1-style tool mediation must
  not become the new shell contract.

## Required V2 owner layers and dependencies

- Shell registry: existing `AdminToolRegistryEntry` for `aws_csm_sandbox`.
- Runtime entrypoint: existing `admin.aws.csm_sandbox_read_only`.
- Semantic owner: reuses AWS operational visibility semantics.
- Port and adapter: same read-only AWS seam, but against the sandbox profile
  root.
- Live state dependency: sandbox AWS profile path only; never the canonical live
  write artifact.

## Admin activity-bar behavior

- Hidden and blocked unless `tool_exposure.aws_csm_sandbox.enabled=true`.
- Visible only to internal-admin audiences even when enabled.
- Must stay visually distinct from production AWS surfaces.

## Carry-forward and do-not-carry-forward

- Keep this as the internal-only staging/sandbox tool.
- Do not expose it on the trusted-tenant portal.
- Do not collapse it into the production `aws` tool id.
