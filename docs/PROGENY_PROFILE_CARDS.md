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
  "progeny_type": "board_member|poc|constituent_farm|...",
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

- `board_member`: `false`
- `poc`: `true`
- `constituent_farm`: `true`

## Sources used by `/portal/network/*`

- Unified optional registry file:
  - `private/progeny/progeny.json`
- Config progeny references in `private/mycite-config-*.json`
- Internal progeny files in `private/progeny/internal/*.json`
- Alias records in `private/aliases/*.json`
- Contracts in `private/contracts/*.json`
- Magnetlinks in `private/magnetlinks/*.json`

Loader precedence is:

1. `private/progeny/progeny.json` entries (if file exists)
2. config-defined progeny refs
3. internal progeny files
4. alias-derived cards (network alias tab)

Cards are deduplicated by `progeny_id`.

## Security boundary

Profile card payloads are metadata only. Secret-like keys are not allowed:

- `secret`
- `token`
- `password`
- `private_key`
- `client_secret`
- `aws_secret_access_key`

## Tenant integration refs (FND)

Tenant progeny metadata for FND integration routing may include:

- `profile_refs.paypal_profile_id`
- `profile_refs.paypal_site_base_url`
- `profile_refs.paypal_checkout_return_url`
- `profile_refs.paypal_checkout_cancel_url`
- `profile_refs.paypal_webhook_listener_url`
- `profile_refs.paypal_checkout_brand_name`
- `profile_refs.aws_profile_id`
- `profile_refs.aws_emailer_list_ref`
- `profile_refs.aws_emailer_entry_ref`

These refs are metadata pointers only and must not include credentials.

## Historical migration note

Legacy non-FND profile-card migrations are preserved in archived portal snapshots under:

- `/srv/compose/portals/unused_portal_sources/2026-03-07-fnd-only/`

## Template reference

See:

- `docs/examples/progeny.unified.example.json`
