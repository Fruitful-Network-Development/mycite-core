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

- Config progeny references in `private/mycite-config-*.json`
- Internal progeny files in `private/progeny/internal/*.json`
- Alias records in `private/aliases/*.json`
- Contracts in `private/contracts/*.json`
- Magnetlinks in `private/magnetlinks/*.json`

## Security boundary

Profile card payloads are metadata only. Secret-like keys are not allowed:

- `secret`
- `token`
- `password`
- `private_key`
- `client_secret`
- `aws_secret_access_key`

## CVCC migration note

Retired standalone NE profile folders (`mycite-ne_dg`, `mycite-ne_eb`, `mycite-ne_jt`, `mycite-ne_ks`) were migrated into CVCC internal progeny cards under:

- `portals/mycite-le_cvcc/private/progeny/internal/`
