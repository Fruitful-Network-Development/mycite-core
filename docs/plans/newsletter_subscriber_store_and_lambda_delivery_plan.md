# Newsletter Subscriber Store and Lambda Delivery Plan

## Purpose

Design a separate newsletter system that is portal-owned, subscriber-driven, and Lambda-delivered without mixing newsletter logic into operator mailbox onboarding profiles.

This is a distinct product lane from AWS-CMS mailbox onboarding.

## Primary outcomes

1. Keep newsletter design separate from operator mailbox profiles.
2. Define a portal-owned subscriber store.
3. Define website signup + unsubscribe flow.
4. Define Lambda delivery orchestration that reads recipients from the portal.
5. Define `news@<domain>` as a distinct sender lane, not an operator mailbox shortcut.

## Architectural judgment

Do not treat `news@<domain>` as just another technical contact mailbox.

There are two distinct systems:

### Operator mailbox system
- technical contact mailboxes
- staged/uninitiated mailboxes
- send-as onboarding
- inbound forwarding/receipt
- operator inbox targets
- per-mailbox operational status

### Newsletter system
- `news@<domain>`
- subscriber list storage
- signup forms
- unsubscribe links
- campaign sending
- delivery audit trail
- Lambda delivery execution

These must remain separate in schema, UI, and control flow.

## Scope

### In scope
- subscriber record model
- newsletter sender identity model
- signup/unsubscribe update model
- portal-owned recipient retrieval
- Lambda delivery orchestration
- campaign/send-job concept
- minimal admin/operator controls

### Out of scope
- operator mailbox onboarding
- technical contact receive-path logic
- legacy forwarder cleanup
- broader CRM/user-resource accounting beyond what newsletter needs

## Core design decisions

### 1. Portal owns subscriber truth
The subscriber list must be a portal-owned canonical store.

Lambda should consume recipients from the portal or a portal-governed data source, not from an unrelated manually maintained file.

### 2. Newsletter sender identity is separate
`news@<domain>` should be represented as a dedicated sender identity lane, separate from technical/operator mailboxes.

### 3. Subscription state is explicit
Every subscriber record must include an explicit `subscribed` boolean.

That boolean must be updated by:
- website signup
- manual admin changes if allowed
- unsubscribe links from emails

## Minimum subscriber data model

Each subscriber record should include at least:
- `email`
- `subscribed` (boolean)
- `created_at`
- `updated_at`
- `unsubscribed_at` (nullable)
- `source` (form/manual/import/etc.)
- `domain` or `list_id`
- optional `name` if later needed

Recommended additions:
- `double_opt_in_status`
- `last_sent_at`
- `bounce_status`
- `suppressed`
- `tags` or `segments` (only if justified later)

Start simple. Do not overdesign the first version.

## Newsletter control-plane model

Define separate concepts such as:

### Newsletter sender config
- sender email (`news@<domain>`)
- domain
- sending provider details
- sender verification status
- template defaults

### Subscriber store
- canonical records
- lookup/update/query by list/domain

### Campaign / send job
- subject
- content/body/template reference
- list selector or query
- send status
- created_at / sent_at
- per-recipient delivery audit if added later

### Lambda delivery job
- fetch recipient stream from portal
- send one email at a time
- respect `subscribed = true`
- respect suppressions/unsubscribes
- write delivery status back if designed in scope

## Signup flow requirements

Website forms should be able to:
1. submit subscriber email to the portal
2. create/update the subscriber record
3. set `subscribed = true`
4. record source and timestamps
5. optionally support double opt-in later

Do not write website signups directly into a disconnected file if the portal is intended to be canonical.

## Unsubscribe flow requirements

Every newsletter email should include an unsubscribe link.

That link should:
1. target a portal endpoint or portal-governed action
2. identify the subscriber safely
3. set `subscribed = false`
4. record `unsubscribed_at`
5. prevent future sends for that subscriber

Do not model unsubscribe as deletion. Keep the record and flip the state.

## Lambda delivery requirements

Lambda should:
- fetch recipients from the portal or a portal-governed export/query
- send one message at a time
- skip unsubscribed recipients
- produce auditable send results
- be separable from operator mailbox logic

Do not make Lambda responsible for subscriber truth itself.

## Portal requirements

The portal should eventually support:
- subscriber list view
- create/update/import subscriber actions
- unsubscribe status view
- sender identity status for `news@<domain>`
- campaign/send job creation
- send progress/status monitoring

This pass can be design-first if implementation is not yet desired, but the plan should preserve a clean boundary from AWS-CMS mailbox onboarding.

## File/data considerations

You mentioned a future file that has not yet been created or decided.

The main design consideration is:
- a file can exist as an implementation detail or export artifact
- but it should not replace the portal as the canonical source of subscriber truth

If an intermediate file/export is used for Lambda, define:
- who generates it
- how it stays in sync
- why it exists
- why it is not the system of record

## Sequence recommendation

### Phase 1 — design and schema
- define newsletter sender model
- define subscriber store schema
- define unsubscribe semantics
- define portal/Lambda boundary

### Phase 2 — portal-owned subscriber store
- add canonical subscriber records
- add signup and unsubscribe endpoints
- add minimal admin view

### Phase 3 — sender and campaign layer
- define `news@<domain>` sender config
- define campaign/send-job model
- define content source path

### Phase 4 — Lambda delivery
- Lambda fetches recipient stream from portal
- sends one message at a time
- records outcome

### Phase 5 — later improvements
- double opt-in
- segmentation
- bounce handling
- suppression lists
- analytics

## Guardrails

Do not:
- fold newsletter sender into operator mailbox profiles
- use technical contact mailbox onboarding as the newsletter control plane
- treat a flat file as the canonical subscriber system
- mix newsletter design with legacy inbound cleanup
- broaden into a full CRM before the core model exists

## Deliverables

Return:
1. newsletter sender model
2. subscriber store schema
3. signup/unsubscribe flow design
4. portal/Lambda boundary design
5. campaign/send-job design
6. files changed or proposed
7. tests run and results if implementation occurs
8. anything intentionally deferred

## Done means

This plan is ready when:
- newsletter is clearly separated from operator mailbox onboarding
- the portal is defined as the canonical subscriber store
- Lambda delivery is defined as a consumer of portal-owned recipient truth
- `subscribed` boolean handling is explicit
- signup and unsubscribe flows are concretely specified
- the path to `news@<domain>` sender support is clear without reintroducing schema drift
