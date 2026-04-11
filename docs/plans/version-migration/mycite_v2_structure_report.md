# MyCite V2 Structure Report

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

This document supersedes the structure proposal in [historical/2-Report.md](historical/2-Report.md) where naming was still too broad.

## Final ontological buckets

- `packages/core/`: pure structures and utilities only
- `packages/state_machine/`: shell, AITAS, NIMM, Hanus, and mediation surface behavior
- `packages/modules/domains/`: domain-semantic owners
- `packages/modules/cross_domain/`: narrow cross-domain owners such as `external_events` and `local_audit`
- `packages/ports/`: explicit capability seams
- `packages/adapters/`: outward implementations
- `packages/tools/`: shell-attached tools
- `packages/sandboxes/`: orchestration boundaries
- `instances/_shared/runtime/`: composition only

## Explicit rejections

- No broad `services/` bucket
- No `packages/core/mediation/`
- No `packages/modules/services/sandboxes/`
- No instance-led placeholder tree as an architecture signal
- No direct recreation of `vault_session/` as one v2 root
