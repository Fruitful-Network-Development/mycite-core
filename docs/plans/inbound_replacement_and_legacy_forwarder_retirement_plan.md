# Inbound Replacement and Legacy Forwarder Retirement Plan

## Purpose

Replace the legacy receipt/forward chain with a portal-native mailbox inbound workflow so mailbox onboarding explicitly includes receive-path modeling, and legacy forwarding infrastructure can later be retired safely.

This pass is about replacement design and migration readiness.

It is not an instruction to immediately delete active legacy infrastructure.

## Primary outcomes

1. Treat inbound receipt/forward as a first-class mailbox concern.
2. Ensure mailbox onboarding is not considered complete until inbound routing is modeled.
3. Replace reliance on the legacy forwarder path for operator workflows.
4. Prepare safe retirement of the legacy chain, including `ses-forwarder-role-l0ypgdpr`.
5. Remove the need to hunt through Gmail spam/junk to complete verification or observe receive-path events.

## Architectural judgment

“Verified send-as” is not enough.

A mailbox must have two explicit operational paths:
- outbound send-as path
- inbound receipt/forward/display path

The current system proved that the legacy forwarder is still active and functionally involved. That means the correct sequence is:
1. build portal-native inbound visibility and control
2. confirm it fully replaces operator reliance on the legacy chain
3. only then remove the legacy chain

Do not reverse that sequence.

## Scope

### In scope
- mailbox-level receive-state modeling
- replacement for legacy forwarder-dependent operator workflows
- portal-visible inbound message metadata/actions
- replay/display path replacement strategy
- dependency inventory for the current legacy chain
- retirement readiness checklist for `ses-forwarder-role-l0ypgdpr`

### Out of scope
- newsletter delivery design
- subscriber data modeling
- broader user/resource tracking
- unrelated AWS cleanup

## Current-state assumptions to preserve

Assume the following are already true:
- FND is the completed reference send-as case
- the portal can now show verification metadata and replay actions
- legacy inbound still exists and is active
- the legacy forwarder role is not removable yet
- replay of captured verification mail still depends on the current legacy path
- Gmail junk placement proved why portal-native visibility is needed

## Target replacement model

The new model should make inbound message handling portal-native.

### Mailbox onboarding completion target
A mailbox should only be considered fully operational when:
- send-as is verified
- inbound routing target is known
- inbound capture/display path is working
- receive-path state is visible in the portal

### Portal-native inbound capabilities
For each mailbox profile, the portal should be able to surface:
- latest captured inbound message metadata
- sender
- recipient
- subject
- capture timestamp
- capture source reference
- extracted verification link/code if applicable
- replay capability if still needed
- receive-path status

### Receive state model
Add or clarify mailbox inbound states such as:
- `receive_unconfigured`
- `receive_configured`
- `receive_pending`
- `receive_verified`
- `receive_operational`
- `receive_legacy_dependent`

These can be derived or explicit, but must be visible and testable.

## Current legacy dependency inventory to preserve and re-check

The agent should assume the legacy chain currently involves things like:
- SES receipt rule set
- receipt rule(s)
- S3 bucket/prefix for inbound capture
- Lambda forwarder
- legacy forwarder role
- `FORWARD_TO`-style routing environment/config

The exact inventory must be revalidated from live state and documented in this pass.

## Replacement design requirements

### Step 1 — Make inbound mailbox state explicit
Extend mailbox profiles so inbound/receive state is modeled separately from send-as verification.

### Step 2 — Promote captured-message display to first-class portal behavior
The portal should no longer depend on the forwarded Gmail copy as the primary human-readable source.

The operator should be able to see:
- the fact a message was captured
- what it was
- what verification link it contains
- what mailbox it belongs to

without depending on Gmail search placement.

### Step 3 — Clarify replay behavior
If replay remains needed, it should be clearly labeled as temporary compatibility behavior while legacy forwarder retirement is still pending.

### Step 4 — Design replacement for legacy forwarding role
Decide whether replay and receive actions should ultimately use:
- direct portal-native display only
- a new Lambda/service surface
- a slimmer replacement role/function
- no replay at all after portal-native display becomes sufficient

### Step 5 — Produce retirement gates
Before `ses-forwarder-role-l0ypgdpr` can be removed, define exact gates such as:
- portal-native verification display complete
- portal-native captured-message visibility complete
- operator workflows no longer require forwarded Gmail copies
- replay no longer depends on legacy Lambda/role
- replacement routing verified for active mailboxes

## Portal/UI requirements

For each mailbox profile, add or strengthen:
- inbound status panel
- latest inbound message metadata card
- received-at timestamp
- verification-link display
- receive-path refresh action
- replay action with compatibility warning if still legacy-dependent
- explicit “legacy dependency” badge until replacement is complete

## API requirements

Use the canonical AWS-CMS admin control plane rather than inventing a second system.

Needed capabilities may include:
- refresh inbound state
- fetch latest captured message metadata
- fetch extracted verification link/code
- replay latest captured inbound message
- mark receive path verified
- report legacy dependency state

If new actions are needed, add them through the existing AWS-CMS admin integration surface.

## Cleanup readiness checklist

This pass must produce a concrete checklist for the later removal pass.

At minimum:
1. identify every live dependency on `ses-forwarder-role-l0ypgdpr`
2. identify which portal features still rely on the legacy chain
3. identify which AWS resources can be removed only after replacement is verified
4. identify which stale policy/resource entries can be cleaned up later
5. identify rollback strategy if replacement fails

## Deliverables

Return:
1. inbound mailbox state model
2. files changed
3. portal/API inbound workflow changes
4. current legacy dependency inventory
5. explicit retirement gates for `ses-forwarder-role-l0ypgdpr`
6. cleanup readiness checklist
7. tests run and results
8. anything intentionally deferred

## Done means

This pass is complete when:
- mailbox onboarding explicitly models inbound state
- the portal can show inbound/captured-message state directly
- operator workflows are less dependent on Gmail mailbox hunting
- the legacy forwarder role has a precise retirement plan
- the system is ready for a later safe removal pass, but the role is not yet removed
