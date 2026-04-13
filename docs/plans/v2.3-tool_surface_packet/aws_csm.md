# AWS-CSM

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Canonical name: `AWS-CSM`\
Packet role: `family_root`\
Queue posture: `next actual build target`\
Current live slice/tool ids: `aws`, `aws_narrow_write`, `aws_csm_sandbox`, `aws_csm_onboarding`

## Current family truth

- The current V2 repo already has live AWS-family admin slices for:
  - read-only AWS visibility
  - bounded AWS narrow-write
  - internal AWS-CSM sandbox visibility
  - AWS-CSM onboarding
- Those current slices remain the implementation truth and keep their existing
  tool ids, entrypoints, and `tool_exposure` keys.
- This family-root doc exists to group them under one canonical AWS operator
  family rather than leaving the packet fragmented across multiple apparent
  roots.

## Family scope

`AWS-CSM` is the single AWS-oriented operator family for:

- AWS visibility and readiness
- bounded AWS writes
- sandbox/staging AWS visibility
- mailbox/domain onboarding
- newsletter-adjacent AWS mailbox/domain operations when they are truly
  AWS-owned

It must not remain fragmented across separate root tools.

## Current slices and crosswalks

Current implemented slice docs under this family:

- [aws.md](aws.md)
- [aws_narrow_write.md](aws_narrow_write.md)
- [aws_csm_sandbox.md](aws_csm_sandbox.md)
- [aws_csm_onboarding.md](aws_csm_onboarding.md)

Legacy crosswalk and retirement docs under this family:

- [aws_platform_admin.md](aws_platform_admin.md)
- [aws_tenant_actions.md](aws_tenant_actions.md)
- [newsletter_admin.md](newsletter_admin.md)

## Next actual implementation target

The next family-level build target is one admin-first, read-only `AWS-CSM`
family landing surface.

That target should:

- compose current AWS visibility and onboarding posture under one family
  identity
- keep shell legality and launch rules exactly where they already live
- keep existing `tool_exposure` semantics and keys unchanged
- avoid inventing a new live family-root tool id during this doc sync

The family landing surface is additive planning above the existing current
implementation slices, not a replacement for their live runtime contracts.

## Do not carry forward

Do not carry forward:

- a separate `aws_platform_admin` root tool
- a separate `aws_tenant_actions` root tool
- a separate `newsletter_admin` root tool
- config-owned launch legality
- broad provider-dashboard sprawl outside shell-owned slices
