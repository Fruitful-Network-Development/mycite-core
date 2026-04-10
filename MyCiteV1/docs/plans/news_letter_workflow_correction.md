# Newsletter Workflow Correction

## Status

Active reference. Updated on April 7, 2026.

## Binding Decisions

- Newsletter is not a standalone tool surface.
- Newsletter mediation lives inside the AWS-CMS surface.
- Canonical newsletter operational profiles stay in:
  `private/utilities/tools/newsletter-admin/newsletter-admin.<domain>.json`
- Canonical subscriber state stays in:
  `/srv/webapps/clients/<domain>/contacts/<domain>-contact_log.json`
- Canonical AWS-hosted admin routes are:
  `/portal/api/admin/aws/newsletter/...`
- The only intended send trigger is an inbound email sent from the selected verified mailbox to `news@<domain>`.
- Manual admin send stays retired and returns an explicit inbound-only error.

## Runtime Rules

- Utility newsletter JSON is non-datum operational state.
- Hidden newsletter secret dotfiles are retired; visible helper state belongs in:
  `private/utilities/tools/newsletter-admin/runtime_secrets.json`
- Progeny `email_policy.newsletter` and `profile_refs.newsletter_*` remain compatibility-read only.
- When progeny newsletter fields disagree with canonical newsletter profile JSON, the portal surfaces warnings and keeps the canonical newsletter profile as the operational source.

## Processing Flow

1. Send the message from the selected verified mailbox to `news@<domain>`.
2. Capture that message through the inbound mail chain.
3. Validate the captured sender against the selected verified AWS-CMS mailbox.
4. Validate the captured recipient against the canonical newsletter list address.
5. Enqueue one SQS dispatch job per subscribed contact.
6. Record dispatch state back into the canonical website contact log.
