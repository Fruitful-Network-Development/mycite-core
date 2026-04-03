# Newsletter System as a Separate Tool: Later Development Context

## Purpose

This document maps out the creation of a newsletter system as a separate service/tool lane rather than an extension of AWS-CMS mailbox onboarding.

The goal is to keep newsletter behavior cleanly separated from operator mailbox profiles while still allowing it to integrate with portal-owned state and AWS-based delivery.

## Why this should be separate

The project now has a stable mailbox-onboarding model in AWS-CMS:
- mailbox profiles are canonical
- send-as and receive-path state are modeled explicitly
- FND is the completed reference mailbox
- TFF/CVCC technical-contact onboarding can proceed from that baseline

That system is for **operator mailboxes**.

Newsletter is a different concern:
- `news@<domain>` sender identity
- subscriber lists
- public signup
- unsubscribe behavior
- campaign creation
- send-job orchestration
- Lambda delivery
- recipient state and audit

These should not be folded into AWS-CMS mailbox profiles.

## Core architectural judgment

Do not treat `news@<domain>` as just another mailbox onboarding profile.

There are now two separate lanes:

### Operator mailbox lane
This covers:
- technical contact mailboxes
- staged but uninitiated operator mailboxes
- send-as onboarding
- receive forwarding/receipt
- operator inbox routing
- mailbox operational state

### Newsletter lane
This should cover:
- newsletter sender identity
- subscriber system of record
- signup/unsubscribe flows
- campaign/send-job records
- Lambda delivery worker behavior

Keeping them separate avoids reintroducing schema drift.

## Current project position

The newsletter lane is still design-only. The current mailbox model in AWS-CMS is the right pattern for grouped state, but it should **not** be overloaded with newsletter sender, subscribers, or campaigns. A repo grep did not reveal an already established newsletter subsystem, so this is a clean new subsystem lane rather than a cleanup of an existing one. fileciteturn58file2

## Recommended product/tool boundary

The cleanest direction is to implement newsletter as a **separate tool** with its own:
- state root
- state adapter
- admin routes
- operator UI
- public subscription endpoints
- Lambda worker boundary

It can still live inside the broader portal ecosystem, but it should not be represented as AWS-CMS mailbox state.

## Recommended system-of-record rule

The portal should own canonical subscriber truth.

That means:
- subscriber records are created, updated, and queried through portal-owned state
- Lambda is a delivery worker, not the source of subscriber truth
- files or exports can exist as job artifacts, but they should not become the canonical system of record

This was the central design recommendation from the planning pass. fileciteturn58file2

## Recommended sender model

A newsletter sender should be modeled separately from mailbox profiles.

Recommended sender config fields:
- `sender_id`
- `tenant_id`
- `domain`
- `sender_email`
- `sender_kind = "newsletter"`
- `delivery_mode = "lambda_ses_api"`
- `aws_region`
- `aws_ses_identity_status`
- `sending_enabled`
- `default_from_name`
- `default_reply_to`
- `configuration_set` nullable
- `last_checked_at`

This is intentionally different from mailbox profiles:
- it does not need operator inbox target
- it does not need Gmail send-as state
- it does not need receive-path modeling

It is an outbound newsletter sender lane, not an operator mailbox lane. fileciteturn58file2

## Recommended subscriber model

Minimum canonical subscriber record:
- `subscriber_id`
- `list_id`
- `tenant_id`
- `domain`
- `email`
- `name` nullable
- `subscribed`
- `suppressed`
- `bounce_status`
- `source`
- `created_at`
- `updated_at`
- `unsubscribed_at` nullable
- `double_opt_in_status` default `not_required`

Minimum list record:
- `list_id`
- `tenant_id`
- `domain`
- `label`
- `sender_id`
- `signup_enabled`
- `created_at`
- `updated_at`

Important design rule:
- `subscribed` is the hard gate for sending
- unsubscribe should not delete a record
- unsubscribe should flip state and preserve history

These were the recommended foundations in the newsletter planning output. fileciteturn58file2

## Recommended public flows

### Signup
Public signup flow should:
1. accept `email`, `list_id`, optional `name`, optional `source`
2. upsert subscriber by `list_id + email`
3. set `subscribed = true`
4. clear `unsubscribed_at`
5. update timestamps
6. optionally support double opt-in later

### Unsubscribe
Each newsletter email should include a signed unsubscribe link that:
1. identifies subscriber and list safely
2. verifies token integrity and expiry
3. sets `subscribed = false`
4. sets `unsubscribed_at`
5. updates `updated_at`

This preserves a consistent audit trail and prevents accidental resends to opted-out recipients. fileciteturn58file2

## Recommended portal/Lambda boundary

The clean design is:

- portal = source of truth
- Lambda = delivery worker

Recommended behavior:
1. portal creates an immutable recipient snapshot from current subscriber truth for a send job
2. Lambda consumes that snapshot
3. Lambda sends one message at a time through SES
4. Lambda writes result events back as job-audit records

This allows repeatable sends and retries while keeping the portal as the canonical record source. The snapshot/export is allowed as a job artifact, not as the canonical system. fileciteturn58file2

## Recommended campaign and send-job model

### Campaign record
Suggested fields:
- `campaign_id`
- `tenant_id`
- `domain`
- `list_id`
- `sender_id`
- `subject`
- `content_ref` or inline body
- `status` (`draft`, `ready`, `sending`, `completed`, `failed`)
- `created_at`
- `updated_at`
- `sent_at` nullable

### Send-job record
Suggested fields:
- `job_id`
- `campaign_id`
- `recipient_snapshot_ref`
- `status`
- `queued_at`
- `started_at`
- `finished_at`
- `attempted_count`
- `sent_count`
- `skipped_count`
- `failed_count`

These separate authoring from execution and let the portal show operational truth cleanly. fileciteturn58file2

## Recommended portal surfaces

Admin/operator surfaces should be separate from AWS-CMS.

Suggested admin capabilities:
- subscriber list view
- add/import/update subscriber
- sender status for `news@<domain>`
- campaign draft/create
- send-job status
- unsubscribe status view

Suggested route split:
- public: `/portal/api/newsletter/...`
- admin: `/portal/api/admin/newsletter/...`

That mirrors the existing admin integration style without mixing newsletter into AWS-CMS mailbox semantics. fileciteturn58file2

## Recommended tool/state layout

The planning output proposed a separate state/tool root such as:

- `/srv/mycite-state/instances/<tenant>/private/utilities/tools/newsletter/`

Suggested state artifacts:
- `newsletter.sender.<tenant>.news.json`
- `newsletter.list.<tenant>.<list_id>.json`
- `newsletter.subscribers.<tenant>.<list_id>.ndjson`
- `newsletter.campaign.<tenant>.<campaign_id>.json`
- `newsletter.send-job.<tenant>.<job_id>.json`
- `newsletter.send-events.<tenant>.<job_id>.ndjson`

Suggested repo files:
- `tools/newsletter/state_adapter/profile.py`
- `portals/_shared/runtime/flavors/fnd/portal/api/newsletter_integrations.py`
- `portals/_shared/runtime/flavors/fnd/portal/ui/static/tools/newsletter_admin.js`
- `portals/_shared/runtime/flavors/fnd/portal/ui/templates/tools/newsletter_admin_home.html`
- `wiki/tools/newsletter-system.md`

These are design targets, not yet implemented files. fileciteturn58file2

## Recommended phased development order

### Phase 1 — schema and contract design
Define sender, list, subscriber, campaign, and send-job contracts.

### Phase 2 — portal-owned subscriber store
Add canonical subscriber records and public signup/unsubscribe endpoints.

### Phase 3 — minimal admin views
Add sender status and subscriber list administration.

### Phase 4 — campaign and recipient snapshot generation
Add campaign creation and snapshot creation.

### Phase 5 — Lambda delivery worker
Have Lambda read the snapshot and send one message at a time through SES.

### Phase 6 — later refinements
Add:
- bounce handling
- suppression
- double opt-in
- segmentation
- analytics

This staged order keeps the system simple and avoids premature overloading.

## Risks if mixed into AWS-CMS

If newsletter is mixed into AWS-CMS mailbox profiles, likely problems include:
- confusion between operator mailboxes and newsletter sender identities
- mixed receive-path and campaign semantics
- bloated mailbox-profile schema
- drift between onboarding state and delivery state
- harder future maintenance

## What should stay deferred

The following remain intentionally deferred for this newsletter lane:
- implementation itself
- bounce/complaint handling
- segmentation
- analytics
- reuse of AWS-CMS mailbox profiles for newsletter sending
- legacy forwarder cleanup

Those should stay separate from the initial newsletter subsystem implementation. fileciteturn58file2

## Recommended deliverables for the later newsletter build pass

The later implementation pass should return:
1. newsletter sender model
2. subscriber store schema
3. signup/unsubscribe endpoint contracts
4. campaign/send-job model
5. portal/Lambda boundary implementation
6. files changed
7. tests run and results
8. anything intentionally deferred

## Summary

The right later-development path is to build newsletter as a **separate tool/service lane** that:
- uses the portal as the canonical subscriber store
- uses Lambda as a delivery worker
- keeps `news@<domain>` separate from operator mailbox onboarding
- introduces campaigns and send jobs without disturbing AWS-CMS mailbox semantics

That gives the project a clean expansion path instead of reintroducing structural confusion.
