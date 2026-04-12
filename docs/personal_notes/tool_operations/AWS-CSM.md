# AWS-CSM

Canonical name: `AWS-CSM`  
Working meaning: one AWS customer/service management family  
Tool family posture: `unify AWS visibility, onboarding, domain/mailbox operations, and newsletter-adjacent AWS work under one tool family`  
Primary exposure: `internal-admin` and `trusted-tenant-admin` by slice  
Primary read/write posture: `read-only + bounded-write sub-slices`

## 1. Completion intent

`AWS-CSM` should be the single AWS-oriented operator tool family.

It should absorb and organize:

- AWS read-only visibility
- mailbox/domain/onboarding flows
- SES / IAM / DNS posture where relevant
- bounded tenant/admin action flows
- newsletter-adjacent operational work where it truly belongs to the AWS mailbox/domain family

It should not remain fragmented across separate root tools.

## 2. Source basis

Repo sources investigated:

- `docs/plans/v2.3-tool_surface_packet/aws.md`
- `docs/plans/v2.3-tool_surface_packet/aws_csm_sandbox.md`
- `docs/plans/v2.3-tool_surface_packet/aws_csm_onboarding.md`
- `docs/plans/v2.3-tool_surface_packet/aws_platform_admin.md`
- `docs/plans/v2.3-tool_surface_packet/aws_tenant_actions.md`
- `docs/plans/v2.3-tool_surface_packet/newsletter_admin.md`
- `docs/wiki/legacy/tools/internal-file-sources.md`
- `docs/contracts/tool_exposure_and_admin_activity_bar_contract.md`

The strongest current V2 evidence shows that the repo already treats AWS read-only, AWS-CSM sandbox, and AWS-CSM onboarding as current V2 surfaces, while separate legacy AWS platform admin and tenant action surfaces crosswalk into those current tools, and standalone `newsletter_admin` is explicitly discarded in favor of AWS-owned slices.

## 3. Core V2.3 position

The correct family shape is one `AWS-CSM` root family with multiple bounded slices, not multiple unrelated root tools.

That family should contain at least these subdomains:

- platform/domain/AWS visibility
- sandbox/staging AWS visibility
- mailbox onboarding and bounded writes
- domain and mail readiness
- newsletter operations only when they are genuinely AWS mailbox/domain operations

## 4. Stable data roots

The investigated docs point to mailbox-profile centered state under:

- `private/utilities/tools/aws-csm/`

That family should remain the canonical operational state root for AWS-CSM profile data.

The mailbox profile, not the domain summary page, is the canonical operational unit.

Newsletter functionality that survives should not create a second standalone root tool. It should operate against AWS-owned domain/mailbox state and explicit contact-list sources.

## 5. Family structure

### 5.1 Slice family A — AWS operational visibility
Current read-only family.

Owns:

- live AWS posture
- domain/mail readiness visibility
- IAM/SES/DNS-facing operator summaries
- read-only platform state

### 5.2 Slice family B — AWS sandbox visibility
Internal-only read-only family.

Owns:

- staging or sandbox AWS posture
- isolated validation and inspection
- internal-only operator work

### 5.3 Slice family C — mailbox / tenant onboarding
Bounded-write family.

Owns:

- mailbox initiation
- staged verification
- onboarding actions
- read-after-write confirmation
- local audit emission

### 5.4 Slice family D — newsletter operations inside AWS-CSM
Later bounded family.

Only valid when the work is truly AWS mailbox/domain aligned, such as:

- send-domain readiness
- newsletter delivery posture
- newsletter contact import queue state
- mailbox/provider-side delivery conditions

Newsletter behavior must not become a second root tool.

## 6. Similarity to FND-EBI

As you noted, `AWS-CSM` should resemble `FND-EBI` in one structural respect:

- it should gather operator meaning from stable filesystem-backed roots rather than from ad hoc UI state

But the authority is different.

- `FND-EBI` derives site analytics and service visibility from site profiles and `analytics/` roots
- `AWS-CSM` derives operator AWS/mailbox/domain meaning from AWS-CSM profile roots and AWS-facing state

## 7. Completion slices

### Slice 1 — unified AWS-CSM read-only home
A read-only surface that can summarize:

- domains
- mailboxes
- current readiness
- AWS posture
- newsletter-adjacent operational flags where applicable

This can be implemented by composing existing `aws`-family read-only surfaces.

### Slice 2 — sandbox/staging view
Internal-only.

### Slice 3 — onboarding and bounded actions
Bounded-write.

### Slice 4 — newsletter operations
Later.

Must remain explicitly AWS-owned and contact-list-source declared.

## 8. Newsletter rule

The repo evidence is clear that standalone `newsletter_admin` should not be rebuilt as its own V2 tool.

Therefore:

- newsletter work belongs inside `AWS-CSM` when it depends on AWS mailbox/domain tooling
- contact-list source inputs must be declared explicitly
- newsletter sending, list updates, and domain readiness must be bounded sub-slices, not a second tool

## 9. Do not carry forward

Do not carry forward:

- a separate `aws_platform_admin` root tool
- a separate `aws_tenant_actions` root tool
- a separate `newsletter_admin` root tool
- broad provider dashboards
- V1 route-family sprawl
- config-driven launch legality

## 10. Acceptance boundary

`AWS-CSM` is complete when AWS visibility, mailbox/domain/onboarding work, and newsletter-adjacent AWS operations can all be expressed as one tool family with bounded slices and one activity-bar identity.

## 11. Recommended V2.3 landing statement

Use `AWS-CSM` as the single AWS operator family. Keep read-only AWS visibility, sandbox AWS inspection, mailbox/domain onboarding, and newsletter-adjacent AWS operations as slices of one tool rather than as separate root tools.
