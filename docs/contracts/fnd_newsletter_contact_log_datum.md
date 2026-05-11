# FND Newsletter Contact Log Datum Contract

Schema: `mycite.v2.datum.fnd.newsletter.contact_log.v1`
Sandbox: `fnd-csm`
Owner: Grantee MSN ID (per grantee profile)

---

## Purpose

Stores the newsletter subscription state and dispatch history for one domain managed by
an FND grantee. This datum migrates from the legacy filesystem format at:
```
/srv/webapps/clients/{domain}/contacts/{domain}-contact_log.json
```

---

## Datum Identity

| Field | Value |
|---|---|
| Sandbox | `fnd-csm` |
| Owner MSN ID | `<grantee_msn_id>` (from grantee profile) |
| Document ID | `fnd::newsletter-contact-log::{domain}` |

Example document IDs:
- `fnd::newsletter-contact-log::trappfamilyfarm.com`
- `fnd::newsletter-contact-log::cvccboard.org`
- `fnd::newsletter-contact-log::fruitfulnetworkdevelopment.com`

---

## Schema Shape

```json
{
  "schema": "mycite.v2.datum.fnd.newsletter.contact_log.v1",
  "domain": "example.com",
  "msn_id": "<grantee_msn_id>",
  "contacts": [
    {
      "email": "subscriber@example.com",
      "subscribed": true,
      "source": "website_signup",
      "last_newsletter_sent_at": "2026-04-01T12:00:00Z",
      "send_count": 3,
      "created_at": "2026-01-15T09:30:00Z"
    }
  ],
  "dispatches": [
    {
      "dispatch_id": "2026-04-01T12:00:00Z",
      "sent_at": "2026-04-01T12:00:00Z",
      "recipient_count": 47
    }
  ],
  "updated_at": "2026-04-01T12:05:00Z"
}
```

---

## Field Reference

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema` | string | Yes | `mycite.v2.datum.fnd.newsletter.contact_log.v1` |
| `domain` | string | Yes | Lowercased domain string, e.g. `trappfamilyfarm.com` |
| `msn_id` | string | Yes | SAMRAS MSN ID of owning grantee |
| `contacts[]` | array | Yes | See Contact Object below |
| `dispatches[]` | array | Yes | Ordered dispatch history (most recent last) |
| `updated_at` | ISO8601 | Yes | Timestamp of last write |

### Contact Object

| Field | Type | Required | Notes |
|---|---|---|---|
| `email` | string | Yes | Lowercased email address |
| `subscribed` | boolean | Yes | `true` = subscribed, `false` = unsubscribed |
| `source` | string | Yes | Subscription source, e.g. `website_signup` |
| `last_newsletter_sent_at` | ISO8601 or `""` | Yes | Empty string if never sent to |
| `send_count` | integer | Yes | Total newsletters dispatched to this contact |
| `created_at` | ISO8601 | No | First recorded subscription timestamp |

---

## Legacy Filesystem Path

```
/srv/webapps/clients/{domain}/contacts/{domain}-contact_log.json
Schema: mycite.webapp.contact_log.v1  (legacy — to be retired post-migration)
```

The new datum schema is backward-compatible with the legacy format. The only additions
are `msn_id` (ownership) and `created_at` per contact (optional).

---

## Access Pattern

**Read:** `FilesystemAwsCsmNewsletterStateAdapter.load_contact_log(domain=domain)` (current)
→ To be replaced by `MosDatumNewsletterContactLogAdapter` (TASK-NEWSLETTER-SQL-ADAPTER)

**Write:** `FilesystemAwsCsmNewsletterStateAdapter.save_contact_log(domain=domain, payload=...)` (current)
→ To be replaced by `MosDatumNewsletterContactLogAdapter.save_contact_log`

The adapter protocol is defined in:
`MyCiteV2/packages/ports/aws_csm_newsletter/contracts.py` — `AwsCsmNewsletterStatePort`

---

## Migration Path

See `TASK-NEWSLETTER-MOS-SEMANTICS-2026-05-10.investigation.md` §6 for bulk import procedure.
See `TASK-NEWSLETTER-SQL-ADAPTER-2026-05-10` for the MOS adapter implementation task.
