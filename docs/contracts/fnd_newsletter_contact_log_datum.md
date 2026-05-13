# FND Newsletter Contact Log Datum Contract

Schema: `mycite.v2.datum.fnd.newsletter.contact_log.v2`
Sandbox: `fnd_csm`
Owner: Grantee MSN ID (per grantee profile)

This is the **v2** contract; it supersedes the v1 schema
`mycite.v2.datum.fnd.newsletter.contact_log.v1` shipped on 2026-05-13.
The v2 row carries each contact's name and email in both ASCII and
SAMRAS bacillete-encoded binary forms, with `name_confirmed` and
`email_confirmed` booleans asserting that the binary form round-trips
losslessly into the system anthology's structural slots.

---

## Purpose

Stores the newsletter subscription state and dispatch history for one
domain managed by an FND grantee. This datum is the **authoritative
source** for site signup, unsubscribe, and dispatcher recipient
enumeration. The legacy filesystem path
`/srv/webapps/clients/{domain}/contacts/{domain}-contact_log.json`
becomes read-only archive after cutover.

---

## Datum Identity

| Field | Value |
|---|---|
| Sandbox | `fnd_csm` |
| Owner MSN ID | `<grantee_msn_id>` (from grantee profile) |
| Canonical name slot | `fnd_newsletter_contact_log_<domain_token>` |
| Document ID | `lv.<msn_id>.fnd_csm.fnd_newsletter_contact_log_<domain_token>.<sha256>` |

`<domain_token>` is the lowercase domain with `.` and `-` replaced by `_`
(e.g. `trappfamilyfarm_com`).

Example document IDs:
- `lv.3-2-3-17-77-1-6-4-1-4.fnd_csm.fnd_newsletter_contact_log_trappfamilyfarm_com.<hash>`
- `lv.3-2-3-17-77-1-6-4-1-4.fnd_csm.fnd_newsletter_contact_log_cuyahogavalleycountrysideconservancy_org.<hash>`

---

## SAMRAS Anchoring

Every contact row references the system anthology's babelette slots:

| Anthology row | Long form | Capacity | Used for |
|---|---|---|---|
| `3-1-4` | `name-babelette` → `niu-baciloid-256-32` (`2-1-3`) | 32 base-256 digits = 32 ASCII bytes | `name_binary` |
| `3-1-9` | `email-babellette` → `niu-baciloid-8-320` (`2-1-8`) | 320 base-8 digits = up to 106 ASCII bytes | `email_binary` |

Encoders live at
`MyCiteV2/packages/core/datum_templates/bacillete.py`. They are
deterministic and lossless within the slot capacity.

---

## Document Structure

### Header rows (layer 0, document-scoped)

| Address | Field | Notes |
|---|---|---|
| `0-0-1` | `schema` | Always `mycite.v2.datum.fnd.newsletter.contact_log.v2` |
| `0-0-2` | `domain` | Lowercased |
| `0-0-3` | `msn_id` | Owning grantee |
| `0-0-4` | `updated_at` | ISO8601 |

### Per-contact rows (layer 1, repeating archetype)

Each row sits at address `1-0-<n>` (n monotonically increasing). Raw
payload shape:

```python
[
    ["1-0-<n>", "~", "0-0-11"],
    {
        "email_ascii":            "subscriber@example.com",
        "email_binary":           "163165142163143162151142145162100145170141155160154145056143157155",  # 320-octal-digit form
        "email_confirmed":        true,
        "name_ascii":             "Subscriber Name",
        "name_binary":            "537562736372696265724e616d65",                                           # hex form
        "name_confirmed":         true,
        "subscribed":             true,
        "source":                 "website_signup",
        "last_newsletter_sent_at": "2026-04-01T12:00:00Z",
        "send_count":             3,
        "created_at":             "2026-01-15T09:30:00Z"
    }
]
```

`name_ascii` may be empty (the dirty CSV contains email-only rows). When
empty, `name_confirmed` is `false`.

### Optional dispatches (reserved)

A future iteration may add per-dispatch rows at layer 2. Reserved but
not yet populated.

---

## Field Reference (per-contact magnitudes)

| Field | Type | Required | Notes |
|---|---|---|---|
| `email_ascii` | string | Yes | Lowercased; canonical lookup key |
| `email_binary` | string | Yes | 0–320 octal digits (3 per ASCII byte) |
| `email_confirmed` | boolean | Yes | `true` iff pure ASCII and ≤106 bytes |
| `name_ascii` | string | No | May be empty |
| `name_binary` | string | No | 0–64 hex chars (2 per ASCII byte) |
| `name_confirmed` | boolean | Yes | `false` when `name_ascii` is empty |
| `subscribed` | boolean | Yes | `false` after unsubscribe click |
| `source` | string | Yes | `website_signup`, `unsubscribe_link`, `csv_import_2026-05-02`, etc. |
| `last_newsletter_sent_at` | ISO8601 or `""` | Yes | Empty for never-sent contacts |
| `send_count` | integer | Yes | Cumulative per contact |
| `created_at` | ISO8601 | No | First subscription / import timestamp |

---

## Read / Write Path

**Read:** `MosDatumNewsletterContactLogAdapter.load_contact_log(*, domain)`
in `MyCiteV2/packages/adapters/sql/newsletter_contact_log.py`. Returns a
dict shaped like the legacy `mycite.webapp.contact_log.v1` for
backward-compatibility with the dispatcher and signup callsites:

```python
{
    "schema": "mycite.v2.datum.fnd.newsletter.contact_log.v2",
    "domain": "<domain>",
    "msn_id": "<grantee_msn_id>",
    "contacts": [
        {
            "email": ...,           # mirrors email_ascii
            "name": ...,            # mirrors name_ascii
            "subscribed": ...,
            "source": ...,
            "last_newsletter_sent_at": ...,
            "send_count": ...,
            "created_at": ...,
            "name_binary": ..., "name_confirmed": ...,
            "email_binary": ..., "email_confirmed": ...,
        },
        ...
    ],
    "dispatches": [],
    "updated_at": ...,
}
```

**Write:** `MosDatumNewsletterContactLogAdapter.save_contact_log(*, domain, payload)`.
Recomputes `*_binary` / `*_confirmed` from `*_ascii` on every save
(idempotent), then `replace_authoritative_document` advances the
version_hash.

The composite adapter
`CompositeAwsCsmNewsletterStateAdapter` wraps the MOS contact-log
adapter PLUS the legacy filesystem profile adapter — contact-log
methods route to MOS, profile/secret methods stay on the filesystem.

---

## Migration

Initial seed: `MyCiteV2/scripts/seed_tff_newsletter_contact_log.py`
ingests
`/srv/webapps/clients/<domain>/contacts/<csv-name>.csv` via the v2
template's `csv_intake_pipeline`, then writes the new datum (replacing
any prior `fnd_newsletter_contact_log_<domain_token>` document if
`--replace-existing` is passed).

Subsequent state changes (signup, unsubscribe, dispatch metrics) flow
through the live signup endpoints which now call the composite adapter
instead of the legacy filesystem one.

---

## Validation Notes

- Document IDs must match the canonical taxonomy regex in
  `MyCiteV2/packages/core/document_naming/__init__.py:148-156`.
- `email_ascii` is the de-dup key for CSV intake; later occurrences
  are dropped.
- A contact whose `email_confirmed` is `false` is still stored — the
  flag exists so operators can audit and choose to drop / re-collect
  problem rows manually.
