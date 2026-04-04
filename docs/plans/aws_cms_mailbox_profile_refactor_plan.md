# AWS-CMS Mailbox-Profile Refactor Plan

## Purpose

Refactor AWS-CMS from a domain-scoped profile model to a mailbox-scoped profile model so each mailbox identity can be onboarded, staged, verified, and operated independently.

This plan must preserve the current stable baseline:
- FND is the completed reference onboarding case
- canonical AWS-CMS admin write/provision paths already exist
- mailbox verification status is now a first-class concern
- newsletter work remains out of scope for this pass

## Primary outcomes

1. Replace the current "one domain profile" assumption with "one mailbox profile".
2. Add mailbox profiles for:
   - `technicalContact@trappfamilyfarm.com`
   - `technicalContact@cuyahogavalleycountrysideconservancy.org`
3. Leave these mailbox profiles staged but un-initiated:
   - `mark@trappfamilyfarm.com`
   - `marilyn@cuyahogavalleycountrysideconservancy.org`
4. Preserve FND as the canonical completed reference mailbox.
5. Keep the current grouped AWS-CMS model coherent rather than overloading the existing TFF/CVCC profiles.

## Architectural judgment

Do not solve this by adding more fields to existing domain profiles.

Each mailbox must become its own canonical operational unit, with its own:
- mailbox profile id
- domain
- send-as address
- operator inbox target
- SMTP secret reference
- initiation state
- verification state
- inbound-routing state
- workflow/completion state

The current AWS-CMS control plane should remain canonical:
- `GET /portal/api/admin/aws/profile/<profile_id>`
- `PUT /portal/api/admin/aws/profile/<profile_id>`
- `POST /portal/api/admin/aws/profile/<profile_id>/provision`

Do not create a second control surface for mailbox onboarding.

## Scope

### In scope
- mailbox-profile data model
- staged vs initiated lifecycle
- mailbox profile naming/identity rules
- profile schema changes
- admin/API/UI updates required to support mailbox profiles
- migration strategy from domain-profile assumptions
- TFF/CVCC technical contact mailbox additions
- staged-but-uninitiated records for Mark and Marilyn

### Out of scope
- newsletter sender design
- subscriber storage
- legacy forwarder removal
- destructive inbound cleanup
- broader resource accounting

## Required mailbox states

Add and consistently use mailbox lifecycle states such as:
- `staged`
- `uninitiated`
- `smtp_configured`
- `send_as_pending`
- `send_as_verified`
- `inbound_pending`
- `inbound_verified`
- `operational`

These do not all need to be single fields; they can be derived from grouped status fields if that remains cleaner. The important thing is that:
- `technicalContact@...` mailboxes can be initiated
- `mark@...` and `marilyn@...` can remain staged but un-initiated
- the UI/API can distinguish them clearly

## Data model targets

Each mailbox profile should minimally support:

### Identity
- `profile_id`
- `domain`
- `mailbox_local_part`
- `send_as_email`
- `operator_inbox_target`
- `tenant_id` or owning domain reference
- `role` or mailbox purpose (`technical_contact`, `operator`, etc.)

### SMTP
- `credentials_secret_name`
- `username`
- `credentials_secret_state`
- `host`
- `port`

### Verification
- `status`
- `portal_state`
- `email_received_at`
- `verified_at`
- latest verification-message metadata reference if available

### Provider
- `aws_ses_identity_status`
- `gmail_send_as_status`
- `last_checked_at`

### Workflow
- `missing_required_now`
- `handoff_status`
- `completion_boundary`
- `initiated`
- `is_ready_for_user_handoff`
- `is_send_as_confirmed`

### Inbound
- `receive_routing_target`
- `receive_state`
- `receive_verified`
- `legacy_forwarder_dependency`
- any captured-message display metadata needed by current portal actions

## Profile naming strategy

Adopt a naming scheme that makes mailbox profiles explicit.

Recommended shape:
- `aws-csm.tff.technicalContact.json`
- `aws-csm.tff.mark.json`
- `aws-csm.cvcc.technicalContact.json`
- `aws-csm.cvcc.marilyn.json`

Alternative accepted shape:
- `aws-csm.mailbox.tff.technicalContact.json`
- `aws-csm.mailbox.cvcc.marilyn.json`

Whichever scheme is chosen, it must:
- be deterministic
- distinguish mailbox from domain
- remain compatible with the canonical admin API paths
- not collide with the existing FND reference profile

## Migration strategy

### Step 1 — Inventory current assumptions
Audit all current AWS-CMS logic, templates, and tests that still assume:
- one profile per domain
- one send-as address per domain
- one operator inbox target per domain

### Step 2 — Introduce mailbox-scoped profile normalization
Refactor normalization/state adapters so mailbox-scoped profiles are first-class and validated.

### Step 3 — Preserve backward compatibility only where needed
If temporary compatibility with the current domain profile naming is needed, make it explicit and short-lived.

### Step 4 — Add the new mailbox profiles
Create mailbox profiles for:
- `technicalContact@trappfamilyfarm.com`
- `technicalContact@cuyahogavalleycountrysideconservancy.org`
- staged/uninitiated `mark@trappfamilyfarm.com`
- staged/uninitiated `marilyn@cuyahogavalleycountrysideconservancy.org`

### Step 5 — Update admin/API/UI surfaces
Ensure the operator can:
- list mailbox profiles by domain
- see initiation state
- see send/receive state separately
- stage but not initiate a mailbox
- begin onboarding for a staged mailbox later

## UI requirements

The portal should show mailbox profiles as separate units, not as flattened fields under a single domain card.

For each mailbox profile, the UI should surface:
- mailbox email
- domain
- purpose/role
- initiation state
- SMTP state
- send-as verification state
- inbound receive state
- operator inbox target
- action buttons relevant to the current state

Required actions should include at least:
- `Refresh Status`
- `Begin Onboarding`
- `Show SMTP Setup`
- `Show Latest Verification Message`
- `Show Verification Link`
- `Replay Verification Forward`
- `Confirm Verified`

For staged/uninitiated mailboxes:
- actions should stop at staging and display
- the UI must not imply they are already initiated

## API/control-plane requirements

Extend the existing canonical admin AWS endpoints rather than inventing new ad hoc write paths.

Needed capabilities:
- mailbox profile save/update
- mailbox profile listing/filtering by domain
- begin-onboarding action
- refresh-provider-status action
- verification-display/replay actions
- confirm-verified action
- inbound-status refresh

## Test requirements

Update or add tests to cover:
- mailbox-profile normalization
- staged/uninitiated mailbox states
- listing mailbox profiles by domain
- preservation of FND as completed reference case
- correct behavior for TFF/CVCC technical contact mailbox additions
- no regression back to single-domain-profile assumptions

## Deliverables

Return:
1. mailbox-profile schema/design changes
2. files changed
3. migration strategy used
4. new mailbox profiles staged
5. UI/API changes
6. tests run and results
7. anything intentionally deferred

## Done means

This pass is complete when:
- AWS-CMS treats mailbox profiles as the canonical operational unit
- `technicalContact@trappfamilyfarm.com` and `technicalContact@cuyahogavalleycountrysideconservancy.org` are added in the new model
- `mark@trappfamilyfarm.com` and `marilyn@cuyahogavalleycountrysideconservancy.org` are staged but un-initiated
- FND remains the completed reference mailbox
- the portal/admin surfaces reflect mailbox-scoped truth rather than domain-scoped shortcuts
