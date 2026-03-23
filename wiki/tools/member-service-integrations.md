# Member Service Integrations

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Tools](README.md)

## Status

Supporting

## Parent Topic

[Tools](README.md)

## Current Contract

Member-scoped service integrations use non-secret metadata in progeny and profile records while queueing or syncing provider-specific runtime work outside portal metadata.

Current documented abstractions are:

- AWS emailer
- PayPal checkout

AWS emailer integration uses non-secret refs such as:

- `aws_profile_id`
- `aws_emailer_list_ref`
- `aws_emailer_entry_ref`
- website analytics metadata fields
- forwarder-only email policy metadata

Current AWS preview endpoint:

- `GET /portal/api/aws/member/<member_id>/emailer_preview`

PayPal checkout integration uses non-secret refs such as:

- `paypal_profile_id`
- `paypal_site_domain`
- `paypal_site_base_url`
- `paypal_checkout_return_url`
- `paypal_checkout_cancel_url`
- `paypal_webhook_listener_url`
- `paypal_checkout_brand_name`

Current PayPal preview endpoint:

- `GET /portal/api/paypal/member/<member_id>/checkout_preview`

Current queue and sync behavior is preview-first. Portal metadata stores routing and context refs only. Credentials and provider runtime state remain outside progeny metadata.

The current tool split is intentional:

- member-scoped actions for profile-specific preview and sync
- platform-scoped admin or agreement tooling for host-level provider state

## Boundaries

This page owns member-service integration abstractions. It does not own:

- hosted shell layout
- secret or credential storage
- general request-log policy
- generic write-pipeline semantics outside provider-specific preview and sync

## Authoritative Paths / Files

- FND provider integration code under `portals/_shared/runtime/flavors/fnd/portal/**`
- profile metadata stored in progeny and hosted-related runtime state

## Source Docs

- `docs/AWS_EMAILER_ABSTRACTION.md`
- `docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md`
- `docs/PROGENY_PROFILE_CARDS.md`

## Update Triggers

- Changes to non-secret member integration refs
- Changes to preview or sync endpoints
- Changes to the split between member-scoped and platform-scoped tooling
- Changes to the secret-storage boundary
