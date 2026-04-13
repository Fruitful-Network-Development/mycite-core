# AWS-CSM

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Canonical name: `AWS-CSM`\
Packet role: `family_root`\
Queue posture: `implemented family root; next slice pending`\
Current live slice/tool ids: `aws`, `aws_narrow_write`, `aws_csm_sandbox`, `aws_csm_onboarding`, `aws_csm_newsletter`

## Current family truth

- The current V2 repo now has a live AWS-CSM family landing surface under the
  existing `aws` tool id in the admin shell.
- That family landing composes:
  - read-only AWS visibility
  - bounded AWS narrow-write as a family sub-surface
  - AWS-CSM onboarding as a family sub-surface
  - AWS-CSM newsletter operations as a family sub-surface
  - internal AWS-CSM sandbox visibility as a gated sub-surface
- The live rollout is FND-first:
  - FND exposes `AWS-CSM` as a single activity-bar family identity
  - FND enables the newsletter sub-surface and canonical AWS-CSM newsletter
    state under the private AWS-CSM root
  - TFF keeps the newsletter sub-surface gated
  - sandbox remains disabled and hidden
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
- newsletter operations are now implemented as a subordinate AWS-CSM family
  surface, not as a standalone tool root

Legacy crosswalk and retirement docs under this family:

- [aws_platform_admin.md](aws_platform_admin.md)
- [aws_tenant_actions.md](aws_tenant_actions.md)
- [newsletter_admin.md](newsletter_admin.md)

## Next family follow-on target

The family landing surface is now implemented. The next AWS-CSM follow-on work
should stay inside the same family root and focus on higher-trust operator
polish such as:

- deeper provider-backed onboarding execution readiness
- sandbox rollout only if a real staged profile path is approved
- family-home polish and recovery behavior without adding new root tool ids

Those follow-ons must keep shell legality and launch rules where they already
live and must keep existing `tool_exposure` semantics unchanged.

## Do not carry forward

Do not carry forward:

- a separate `aws_platform_admin` root tool
- a separate `aws_tenant_actions` root tool
- a separate `newsletter_admin` root tool
- config-owned launch legality
- broad provider-dashboard sprawl outside shell-owned slices
