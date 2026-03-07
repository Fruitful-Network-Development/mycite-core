# AWS Emailer Abstraction (Prototype)

## Purpose

Define how tenant-scoped AWS tooling consumes anthology abstractions without storing secrets in portal metadata.

Current prototype anchor:

- list abstraction datum: `10-0-1` (`emailer_list`)
- entries referenced under that list (for example `9-2-*`)

Portal runtime resolves this structure and produces a deterministic preview payload before queueing AWS work.

## Tenant metadata keys

Tenant profile metadata remains non-secret and now supports:

```json
"profile_refs": {
  "aws_profile_id": "aws:tenant:<tenant_id>",
  "aws_emailer_list_ref": "10-0-1",
  "aws_emailer_entry_ref": "9-2-1"
}
```

- `aws_emailer_list_ref`: required for AWS emailer preview.
- `aws_emailer_entry_ref`: optional hint/fallback for entry row typing.

## Preview endpoint

- `GET /portal/api/aws/tenant/<tenant_id>/emailer_preview`

The endpoint:

1. loads tenant `profile_refs`
2. resolves `aws_emailer_list_ref` against anthology
3. expands entry rows and contact collection rows
4. derives subscription booleans from bool reference pairs
5. returns summary counts and warnings

## Format definitions

`dns_wire_format`

Hex rendering of a domain name in DNS wire format. Each domain label is prefixed by a one-byte length, and the name ends with `00`. This format is used for DNS lookups and encodes the domain only, not the email local-part before `@`. Maximum size: 255 bytes.

`text_byte_email_format`

Hex rendering of the full email address as literal text bytes. It stores the entire mailbox string exactly as written, including the local-part, `@`, dots, and domain, so it can be reconstructed losslessly. This format is for storage/serialization, not DNS lookup. Maximum size: 320 bytes raw, or 321 bytes with an optional trailing `00` terminator.

## Queue integration

AWS proxy currently accepts queued preview payloads only:

- `POST /api/admin/aws/tenant/<tenant_id>/provision`
- action: `emailer_sync_preview`
- payload:
  - `emailer_preview`
  - `format_hint` (optional)

No direct SES send is performed in this milestone.
