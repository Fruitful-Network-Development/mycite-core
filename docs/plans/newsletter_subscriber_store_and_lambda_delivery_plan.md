# Newsletter Contact Log and Lambda Delivery Plan

## Purpose

Describe a future newsletter system that is separate from AWS-CMS mailbox
onboarding and uses a website-owned contact log plus Lambda delivery.

## Core Judgment

Do not treat newsletter delivery as an extension of operator mailbox onboarding.

Two different systems exist:

- AWS-CMS mailbox onboarding
- newsletter contact-list and delivery management

They must remain separate in schema, UI, and runtime control flow.

## Canonical Data Location

The canonical mailing-list file should live under the website client tree:

- `/srv/webapps/clients/<domain>/contacts/<domain>-contact_log.json`

This is the system of record for newsletter recipients.

It is not:

- an AWS-CMS mailbox file
- a tenant-private utility file
- a Lambda-owned data file

## Minimum Contact Record

Each JSON entry should include:

- `email`
- `name` nullable
- `subscribed`
- `source`
- `created_at`
- `updated_at`
- `unsubscribed_at` nullable
- `domain`
- `list_id`

Later additions may include:

- `double_opt_in_status`
- `suppressed`
- `bounce_status`
- `last_sent_at`

## Admin Service Tool Responsibilities

The future service tool should:

- read and validate `<domain>-contact_log.json`
- append new contacts
- update existing contacts
- record imports
- mark unsubscribes by toggling `subscribed=false`
- provide admin-facing status and audit views

This tool is for admin email-list management. It belongs beside the website
tree, not under `private/utilities/tools`.

## Signup Flow

Website signup should:

1. receive `email`, optional `name`, `domain`, and `list_id`
2. resolve `/srv/webapps/clients/<domain>/contacts/<domain>-contact_log.json`
3. insert or update the matching record
4. set `subscribed=true`
5. clear `unsubscribed_at`
6. update timestamps

## Unsubscribe Flow

Each newsletter email should include a signed unsubscribe link.

That flow should:

1. identify the contact safely
2. resolve the canonical contact-log JSON file
3. update the matching record
4. set `subscribed=false`
5. set `unsubscribed_at`
6. prevent future sends to that contact

Unsubscribe should never delete the record.

## Lambda Delivery Boundary

Lambda should:

- read a deliberate recipient snapshot derived from the website contact log
- send one email at a time
- respect `subscribed=true`
- skip unsubscribed or suppressed recipients
- emit auditable send results

Lambda should not become the source of contact truth.

## AWS-CMS Separation Rule

AWS-CMS onboarding must not mutate newsletter contact lists.

Required separation:

- AWS-CMS provisioning endpoints reject newsletter/contact-list actions
- newsletter unsubscribe or signup work does not run through AWS-CMS mailbox
  routes
- mailbox onboarding state and newsletter contact-list state stay in separate
  files and separate tools

## Suggested Future Tests

When implementation begins, tests should prove:

- signup appends a new JSON contact entry in the correct website path
- signup updates an existing entry without duplicating it
- unsubscribe links toggle `subscribed=false` on the matching record
- Lambda recipient selection skips unsubscribed contacts
- AWS-CMS endpoints reject newsletter/contact-list actions

## Operational Reminder

This model depends on correct live-path alignment.

- deploy tooling must preserve `/srv/webapps/clients/<domain>/contacts/`
- runtime scripts must not silently redirect newsletter data back into older
  tenant-private locations
- restart scripts should be validated alongside portal deploy scripts so the
  live service does not drift away from the canonicalized paths
