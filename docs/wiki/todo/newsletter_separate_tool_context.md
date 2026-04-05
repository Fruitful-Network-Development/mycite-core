# Newsletter Contact Lists as a Separate Service-Tool Pattern

## Purpose

Define newsletter list management as a separate service-tool lane that does not
reuse AWS-CMS mailbox onboarding state.

AWS-CMS remains the operator mailbox onboarding system.
Newsletter contact lists are a different concern.

## Boundary From AWS-CMS

AWS-CMS owns:

- operator mailbox profiles
- SMTP secret readiness
- Gmail send-as handoff and verification state
- inbound receive-path state

Newsletter contact-list tooling should own:

- website mailing-list records
- signup and unsubscribe updates
- newsletter sender/list metadata
- Lambda delivery job inputs

Do not:

- store newsletter list data in AWS-CMS mailbox profiles
- store newsletter list data under `private/utilities/tools/aws-csm`
- route unsubscribe behavior through AWS-CMS onboarding actions

## Canonical Contact-List Location

Canonical mailing-list data should live with the website that owns it.

Required path pattern:

- `/srv/webapps/clients/<domain>/contacts/<domain>-contact_log.json`

Example:

- `/srv/webapps/clients/trappfamilyfarm.com/contacts/trappfamilyfarm.com-contact_log.json`

This mirrors the FND-EBI pattern, where analytics are mediated from
`client_root/analytics` instead of being stored as tenant-private tool state.

## Service-Tool Role

The newsletter contact-list tool is an admin email-list management surface.

It should:

- append new contacts
- update existing contacts by `email` plus `list_id` or domain context
- mark unsubscribes by toggling `subscribed=false`
- preserve history with timestamps instead of deleting records

It is not a tenant-private utility. Its canonical data belongs alongside the
public site's `webapps/clients/<domain>` tree.

## Minimum Contact-Log Record

Each entry should include at least:

- `email`
- `name` nullable
- `subscribed`
- `source`
- `created_at`
- `updated_at`
- `unsubscribed_at` nullable
- `domain`
- `list_id`

Optional later fields:

- `double_opt_in_status`
- `bounce_status`
- `suppressed`
- `last_sent_at`
- `tags`

## Signup Flow

Public signup should:

1. accept `email`, optional `name`, `domain`, and `list_id`
2. open `/srv/webapps/clients/<domain>/contacts/<domain>-contact_log.json`
3. upsert the matching record
4. set `subscribed=true`
5. clear `unsubscribed_at`
6. update `updated_at`

## Unsubscribe Flow

Every newsletter email should include a signed unsubscribe link.

That link should:

1. identify the subscriber safely
2. resolve the canonical website contact-log path
3. update the matching JSON entry
4. set `subscribed=false`
5. set `unsubscribed_at`
6. update `updated_at`

Unsubscribe is a state change, not record deletion.

## Lambda Boundary

Lambda remains a delivery worker.

Recommended flow:

1. the admin service tool reads the canonical website contact log
2. it creates a recipient snapshot for a send job
3. Lambda consumes that snapshot
4. Lambda sends one email at a time
5. Lambda respects `subscribed=true` as the hard delivery gate

The canonical list remains the website contact-log file, not the Lambda worker.

## Suggested Repo Surface

Suggested future repo code:

- `packages/tools/newsletter/...`
- `instances/_shared/runtime/flavors/fnd/portal/api/newsletter_integrations.py`
- `instances/_shared/runtime/flavors/fnd/portal/ui/static/tools/newsletter_admin.js`
- `instances/_shared/runtime/flavors/fnd/portal/ui/templates/tools/newsletter_admin_home.html`

Suggested runtime behavior:

- code lives in the repo
- canonical contact data lives under `/srv/webapps/clients/<domain>/contacts/`

## Testing Expectations

When implemented, tests should prove:

- signup appends or updates the correct JSON entry in
  `<domain>-contact_log.json`
- unsubscribe links toggle `subscribed=false` on the matching JSON entry
- unsubscribed contacts are skipped by newsletter delivery logic
- AWS-CMS provisioning routes reject newsletter/contact-list actions so contact
  list changes are not mixed into mailbox onboarding

## Guardrails

Do not:

- treat `news@<domain>` as a technical-contact mailbox
- reuse AWS-CMS `profile_id` JSON as the subscriber store
- move website contact logs into `private/utilities/tools`
- mix newsletter contact-list work with legacy inbound cleanup

## Operational Note

Because this pattern depends on canonical website-root paths, deploy scripts and
admin tooling must preserve those paths on deploy and restart. Path drift back
to older private-tool locations would create split-brain list state.
