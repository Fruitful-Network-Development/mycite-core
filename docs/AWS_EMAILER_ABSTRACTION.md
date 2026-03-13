# AWS Emailer Abstraction

## Purpose

Define how member-scoped AWS tooling consumes anthology abstractions without storing secrets in portal metadata.

Current anchor:

- list abstraction datum: `10-0-1` (`emailer_list`)
- entries referenced under that list (for example `9-2-*`)

Portal runtime resolves this structure and produces a deterministic preview payload before queueing AWS work.

## Tool split

The current tool split is intentional:

- `AWS Member Actions`
  - member-scoped preview/sync/provision requests
- `AWS Platform/Admin`
  - FND-scoped platform status

These are separate because they operate on different scopes and APIs, not because of accidental duplication.

## Member metadata keys

Member profile metadata remains non-secret and now supports:

```json
"profile_refs": {
  "aws_profile_id": "aws:member:<member_id>",
  "aws_emailer_list_ref": "10-0-1",
  "aws_emailer_entry_ref": "9-2-1"
}
```

- `aws_emailer_list_ref`: required for AWS emailer preview.
- `aws_emailer_entry_ref`: optional hint/fallback for entry row typing.

Forwarder/no-SMTP newsletter routing is defined in member metadata too:

```json
"email_policy": {
  "mode": "forwarder_no_smtp",
  "smtp_enabled": false,
  "forwarder_address": "proxy@tenant.example",
  "operator_inbox": "tenant.operator@gmail.com",
  "poc_address": "mark@tenant.example",
  "inbound_aliases": ["info@tenant.example", "mark@tenant.example"],
  "reply": {
    "allowed_from": ["mark@tenant.example"],
    "send_as": ["info@tenant.example", "mark@tenant.example"],
    "send_as_policy": "original_contacted_alias"
  },
  "newsletter": {
    "allowed_from": ["mark@tenant.example"],
    "ingest_address": "hermes@tenant.example",
    "sender_address": "news@tenant.example",
    "dispatch_mode": "aws_internal"
  }
}
```

This keeps SMTP disabled at the progeny profile layer while preserving deterministic routing metadata for queued AWS newsletter processing.

## Preview endpoint

- Canonical: `GET /portal/api/aws/member/<member_id>/emailer_preview`
- Legacy alias: `GET /portal/api/aws/tenant/<tenant_id>/emailer_preview`

The endpoint:

1. loads member `profile_refs`
2. resolves `aws_emailer_list_ref` against anthology
3. expands entry rows and contact collection rows
4. derives subscription booleans from bool reference pairs
5. returns summary counts, warnings, and non-secret member routing metadata

## Format definitions

`dns_wire_format`

Hex rendering of a domain name in DNS wire format. Each domain label is prefixed by a one-byte length, and the name ends with `00`. This format is used for DNS lookups and encodes the domain only, not the email local-part before `@`. Maximum size: 255 bytes.

`text_byte_email_format`

Hex rendering of the full email address as literal text bytes. It stores the entire mailbox string exactly as written, including the local-part, `@`, dots, and domain, so it can be reconstructed losslessly. This format is for storage/serialization, not DNS lookup. Maximum size: 320 bytes raw, or 321 bytes with an optional trailing `00` terminator.

## Queue integration

AWS admin/runtime currently accepts queued preview payloads only:

- `POST /api/admin/aws/tenant/<tenant_id>/provision`
- action: `emailer_sync_preview`
- payload:
  - `emailer_preview`
  - `format_hint` (optional)

No direct SES send is performed in this phase.
