# Progeny Profile Cards

## Purpose

Profile cards provide a non-secret relationship view for network tabs.
They are JSON-backed and independent from UI implementation details.

## Canonical schema

```json
{
  "schema": "mycite.progeny.profile_card.v1",
  "progeny_id": "stable-card-id",
  "msn_id": "3-2-...",
  "progeny_type": "member|poc|user|constituent_farm|...",
  "display": {
    "title": "Human readable title",
    "subtitle": "Optional subtitle"
  },
  "contact": {
    "name": "Optional",
    "email": "Optional"
  },
  "alias_expected": false,
  "status": {
    "state": "active|suspended",
    "note": "Optional"
  },
  "source": {
    "kind": "config_ref|internal_json|alias_json|migration",
    "ref": "source reference"
  }
}
```

## Alias expectation defaults by type

- `member`: `false`
- `poc`: `true`
- `constituent_farm`: `true`

## Sources used by `/portal/network/*`

- Unified optional registry file:
  - `private/progeny/progeny.json`
- Config progeny references in active config:
  - `private/config.json` (canonical)
  - `private/mycite-config-*.json` (legacy fallback)
- Internal progeny files in `private/progeny/internal/*.json`
- Alias records in `private/aliases/*.json`
- Contracts in `private/contracts/*.json`
- Auto-seeded local progeny profiles generated from config refs when missing:
  - `private/progeny/<ref-from-config>.json`

Loader precedence is:

1. `private/progeny/progeny.json` entries (if file exists)
2. config-defined progeny refs
3. internal progeny files
4. alias-derived cards (network alias tab)

Cards are deduplicated by `progeny_id`.

## Local progeny seed behavior

When a portal config includes progeny refs that do not have backing files yet, runtime creates local profile-card files with:

- `schema = mycite.progeny.profile_card.v1`
- `source.kind = config_ref_seed`
- `source.local_only = true`
- non-secret defaults only

This allows local/prototype progeny to exist without alias linkage.

## Security boundary

Profile card payloads are metadata only. Secret-like keys are not allowed:

- `secret`
- `token`
- `password`
- `private_key`
- `client_secret`
- `aws_secret_access_key`

## Member integration refs (FND)

Member progeny metadata for FND integration routing may include:

- `profile_refs.paypal_profile_id`
- `profile_refs.paypal_site_domain`
- `profile_refs.paypal_site_base_url`
- `profile_refs.paypal_checkout_return_url`
- `profile_refs.paypal_checkout_cancel_url`
- `profile_refs.paypal_webhook_listener_url`
- `profile_refs.paypal_checkout_brand_name`
- `profile_refs.aws_profile_id`
- `profile_refs.aws_emailer_list_ref`
- `profile_refs.aws_emailer_entry_ref`
- `profile_refs.email_transport_mode`
- `profile_refs.email_forwarder_address`
- `profile_refs.email_operator_inbox`
- `profile_refs.email_poc_address`
- `profile_refs.newsletter_ingest_address`
- `profile_refs.newsletter_sender_address`

Recommended non-secret member policy block:

- `email_policy.mode = forwarder_no_smtp`
- `email_policy.smtp_enabled = false`
- `email_policy.inbound_aliases[]`
- `email_policy.reply.allowed_from[]`
- `email_policy.reply.send_as[]`
- `email_policy.newsletter.ingest_address`
- `email_policy.newsletter.sender_address`
- `email_policy.newsletter.dispatch_mode`

These refs are metadata pointers only and must not include credentials.

## Legacy terminology compatibility

- `tenant` and `board_member` are accepted legacy labels.
- Runtime normalizes both toward canonical `member` in shared card/build flows.
- FND APIs expose canonical `member` endpoints and keep `tenant` aliases for compatibility.

## Historical migration note

Legacy non-FND profile-card migrations are preserved in archived portal snapshots under:

- `/srv/compose/portals/unused_portal_sources/2026-03-07-fnd-only/`

## Template reference

See:

- `docs/examples/progeny.unified.example.json`
