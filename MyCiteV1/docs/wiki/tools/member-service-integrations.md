# Member Service Integrations

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Tools](README.md)

## Status

Supporting

## Parent Topic

[Tools](README.md)

## Current Contract

Member-scoped service integrations use non-secret metadata in progeny and profile records while queueing or syncing provider-specific runtime work outside portal metadata.

Current documented abstractions are:

- PayPal checkout

AWS-CMS is no longer part of the member-service integration surface. The active AWS-CMS tool is operator-only and is staged through `private/utilities/tools/aws-csm/` in tool mode. It does not use member preview endpoints, newsletter flows, or `private/admin_runtime/aws/...`.

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

Current queue and sync behavior for member integrations is preview-first. Portal metadata stores routing and context refs only. Credentials and provider runtime state remain outside progeny metadata.

Current FND-side service-management tools are mediation-oriented:

- PayPal, analytics, and keycloak-backed portal operations remain separate tools
- each tool reads its own JSON collection under `private/utilities/tools/<tool-id-or-namespace>/`
- shared shell mediation treats those files as profile-card oriented config-context collections rather than container-era proxy state

`fnd_ebi` extends this pattern with shared-core internal file reads:

- profile members provide `domain` and `site_root`
- shared core derives analytics paths from `site_root` and reads those files in read-only mode
- derived analytics files are exposed as internal source members inside config-context
- mediated dashboard cards are rebuilt from live analytics files on refresh (not static profile identity rendering)
- default mediation modes are now `Overview`, `Traffic`, `Events`, `Errors / Noise`, and `Files`
- card summaries separate human-like browsing, crawler/indexing traffic, and hostile/probe noise where detectable
- warnings explicitly surface missing/unreadable/stale file conditions and no-event/no-robots conditions

## Boundaries

This page owns member-service integration abstractions. It does not own:

- hosted shell layout
- secret or credential storage
- general request-log policy
- generic write-pipeline semantics outside provider-specific preview and sync
- AWS-CMS operator staging

## Authoritative Paths / Files

- FND provider integration code under `instances/_shared/runtime/flavors/fnd/portal/**`
- profile metadata stored in progeny and hosted-related runtime state

## Source Docs

- `docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md`
- `docs/PROGENY_PROFILE_CARDS.md`

## Update Triggers

- Changes to non-secret member integration refs
- Changes to preview or sync endpoints
- Changes to the member-integration secret-storage boundary
