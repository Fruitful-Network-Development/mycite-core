# Legacy Inbound Removal and Replacement Context

## Purpose

This document records the current state, rationale, dependencies, risks, and recommended sequence for removing the legacy inbound forwarding chain that is still partially supporting AWS-CMS mailbox workflows.

It is meant to serve as a later-development reference, not as an instruction to remove anything immediately.

## Current baseline

The project has already completed two major transitions:

1. AWS-CMS now uses **mailbox profiles** as the canonical operational unit instead of one profile per domain.
2. Inbound/receive-path state is now modeled as a **first-class mailbox concern**, not as a hidden side effect of send-as completion.

That means the legacy inbound chain is no longer the primary source of operator truth, but it is **still active** and still supports at least one remaining operator action.

## Why this document exists

A full removal of legacy inbound is now possible to map precisely, but **not yet safe to execute**.

The reason is simple:

- Portal-native capture/metadata/link display now exists.
- Portal-native receive-path modeling now exists.
- But **replay of captured verification mail still depends on the legacy chain**.

So the correct objective is:

- finish the replacement surface,
- verify that active mailbox workflows no longer require the legacy chain,
- then remove the legacy chain deliberately.

## Confirmed current architecture

### Mailbox model

AWS-CMS now treats mailbox profiles as canonical. The live active state root contains mailbox-scoped files such as:
- `aws-csm.fnd.dylan.json`
- `aws-csm.tff.technicalContact.json`
- `aws-csm.tff.mark.json`
- `aws-csm.cvcc.technicalContact.json`
- `aws-csm.cvcc.marilyn.json`

The old TFF/CVCC domain profiles were retired from the active root and moved into migration backups. The active tool member list was updated so mediation/config-context uses the mailbox set rather than the retired domain files. fileciteturn58file0

### Inbound model

AWS-CMS now derives and exposes inbound-first state such as:
- `inbound.receive_state`
- `inbound.portal_native_display_ready`
- `inbound.legacy_dependency_state`
- `inbound.legacy_replay_available`
- `workflow.inbound_blockers_now`
- `workflow.operational_blockers_now`
- `workflow.is_receive_path_modeled`
- `workflow.is_receive_path_confirmed`
- `workflow.is_portal_native_inbound_ready`
- `workflow.is_mailbox_operational`

This means the project now has a real receive-path model, not just a send-as model. fileciteturn58file1

### Canonical control plane

The canonical admin AWS-CMS control surface remains the existing admin integration endpoints, not a second ad hoc write plane. The admin surface already supports profile reads/writes and provision actions through the portal API in `admin_integrations.py`. fileciteturn56file0

## What the legacy inbound chain still is

The currently revalidated legacy chain includes:
- SES receipt rule set `fnd-inbound-rules`
- receipt rule `mode-a-forward-dcmontgomery`
- S3 bucket `ses-inbound-fnd-mail`
- S3 prefix `inbound/`
- Lambda `ses-forwarder`
- IAM role `ses-forwarder-role-l0ypgdpr`
- Lambda environment routing to `dylancarsonmontgomery@gmail.com`

This chain is still live and still participating in real mail flow. fileciteturn58file1

## What has already been replaced by the portal

The portal now provides native visibility for:
- latest captured message metadata
- capture-reference display
- extracted verification-link display
- receive-path refresh
- operator receive-path confirmation

This is the critical replacement progress: the operator no longer needs the legacy chain to be the only place where receive-path truth is visible. fileciteturn58file1

## What still depends on legacy inbound today

The important remaining dependency is:

- **Replay of captured verification mail still depends on `ses-forwarder` and `ses-forwarder-role-l0ypgdpr`.**

That means the legacy role and forwarder are currently **active legacy**, not removable residue. The portal-native display is already enough to see the captured message and its verification context, but the system still uses the old chain to replay the message into Gmail when needed. fileciteturn58file1

## Why the legacy chain should still be removed later

Even though it still functions, it should not remain the long-term baseline because:

1. It keeps a hidden dependency between mailbox onboarding and old forwarding infrastructure.
2. It preserves behavior that encourages mailbox hunting in Gmail instead of portal-native operator workflows.
3. It mixes old routing assumptions into a system that is otherwise now mailbox-scoped and explicitly modeled.
4. It complicates future maintenance, IAM understanding, and cleanup.
5. It leaves old resource-policy and invoke-permission surfaces in place longer than needed.

## Current removal blockers

The legacy chain should not be removed yet because at least these conditions still apply:

- replay still uses the old forwarder
- the operator workflow still has a compatibility branch that relies on forwarded copies
- the replacement path for replay or equivalent operator convenience is not yet complete
- rollback planning must exist before destructive cleanup

## Retirement gates

The later removal pass should not begin until all of the following are true:

1. **Portal-native message display verified**
   - the portal can show latest captured message metadata reliably
   - the portal can display capture references and verification context reliably

2. **Portal-native verification-link display verified**
   - the operator can get the link directly from the portal for all intended mailbox cases

3. **Operator workflow no longer depends on forwarded Gmail copies**
   - inbox search should not be required for normal onboarding
   - spam/junk placement should no longer be the deciding factor in whether the operator can proceed

4. **Replay removed or replaced**
   - either replay is no longer needed,
   - or replay is implemented through a new non-legacy surface that does not depend on `ses-forwarder-role-l0ypgdpr`

5. **Rollback path defined**
   - if replacement behavior fails, the team must know whether and how to temporarily restore the older path

6. **Mailbox receive-path confirmation works without the legacy route**
   - the receive model in AWS-CMS must remain truthful after removal

These gates were already identified in the live readiness work and should remain the formal preconditions for removal. fileciteturn58file1

## Recommended removal sequence

### Phase 1 — preserve and observe
Keep the current legacy chain intact while mailbox onboarding and receive-path confirmation continue to use the newer portal-native visibility surfaces.

### Phase 2 — replace replay
Implement a non-legacy replacement for replay, or explicitly decide replay is unnecessary once portal-native display and link surfacing are sufficient.

### Phase 3 — verify no active workflow still depends on forwarding
Test the onboarding flow for active mailbox profiles without relying on forwarded Gmail copies as the primary operator view.

### Phase 4 — stage cleanup plan
Prepare exact cleanup operations for:
- Lambda invoke dependencies
- role usage
- receipt rule references
- stale resource-policy entries
- stale invoke-policy entries

### Phase 5 — remove legacy chain deliberately
Only when all gates are satisfied:
- remove replay dependency
- remove/replace `ses-forwarder`
- remove/replace `ses-forwarder-role-l0ypgdpr`
- clean receipt-rule Lambda actions if they are no longer needed
- clean stale Lambda invoke-policy entries

### Phase 6 — post-removal verification
Confirm:
- portal-native receive-path workflows still function
- mailbox operational state remains truthful
- no onboarding path silently regressed

## Risks if removed too early

If the chain is removed before the replacement boundary is truly complete, likely failures include:
- loss of replay capability
- loss of operator convenience during verification flows
- false “receive-ready” state in the portal
- emergency rollback through poorly documented legacy resources
- confusion about whether a failure is in AWS-CMS or in removed legacy infrastructure

## IAM and policy context

One currently attached inline policy on the EC2 role is conceptually obsolete for the current SMTP model:

- `AWSCMSManageSmtpCredentials`

This policy was based on IAM service-specific credential assumptions. The active SES SMTP model is access-key-based through `aws-cms-smtp`, so future logic should not be built around service-specific credential actions. This does not directly block legacy inbound removal, but it is part of the current operational context and should remain classified as stale policy rather than part of the intended long-term design. fileciteturn57file0

## What should not be mixed into this pass

The later legacy inbound cleanup/removal pass should stay separate from:
- newsletter design and implementation
- subscriber storage
- resource-control features
- broad mailbox-profile schema refactors
- unrelated AWS cleanup

Those are separate development lanes now.

## Recommended deliverables for the later removal pass

The later pass should return at minimum:
1. exact dependency inventory revalidated from live state
2. replacement status for replay
3. exact resources to remove or replace
4. rollback plan
5. files changed
6. tests run and live verification results
7. explicit confirmation that `ses-forwarder-role-l0ypgdpr` is no longer required

## Summary

The project is now in the correct position to plan a later legacy inbound removal, but not yet to perform it blindly.

The important present truth is:

- mailbox modeling is modernized
- inbound state is modeled directly
- portal-native visibility exists
- the legacy chain is no longer the primary source of truth
- but replay still depends on it

So the next later-development objective is not “delete legacy inbound,” but:

**replace the last remaining dependency cleanly, then remove legacy inbound from a position of clarity.**
