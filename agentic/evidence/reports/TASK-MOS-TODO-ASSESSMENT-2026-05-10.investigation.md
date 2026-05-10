# Investigation Report: MOS Migration TODO Assessment

**Task:** TASK-MOS-TODO-ASSESSMENT-2026-05-10  
**Date:** 2026-05-10  
**Disposition:** DEFER — prerequisites not met

---

## Finding Summary

Three TODO sites in `app.py` (lines ~1201, ~1229, ~1287) mark contact log
filesystem writes that are intended to eventually migrate to MOS datum upserts.
All three are working correctly today. No MOS SQL adapter for newsletter state
exists. Migrating before the ownership model and schema are defined would produce
non-canonical datum IDs incompatible with future audit and directive requirements.

---

## A. Current Filesystem Operations

All three sites write to the same path:
```
/srv/webapps/clients/{domain}/contacts/{domain}-contact_log.json
```
Schema: `mycite.webapp.contact_log.v1`  
Write method: atomic temp-file + rename via `_write_contact_log_atomic()`

| Site | Endpoint | Mutation |
|---|---|---|
| Line ~1201 | `POST /__fnd/newsletter/subscribe` | `_upsert_subscriber()` — insert or re-subscribe one contact in `contacts[]` |
| Line ~1229 | `POST /__fnd/newsletter/unsubscribe` | Update one contact: `subscribed=False`, `source="unsubscribe_link"`, `unsubscribed_at=now` |
| Line ~1287 | `POST /__fnd/newsletter/dispatch-result` | Dual update: `dispatches[].results[email]` status AND `contacts[].last_newsletter_sent_at` + `send_count` when status=sent |

All three are the same schema, path, and write mechanism. Mutations are different:
one insert, one flag update, one dual-object update.

---

## B. MOS Adapter Readiness

**Port exists:** `AwsCsmNewsletterStatePort` in `packages/ports/aws_csm_newsletter/contracts.py`  
Methods: `load_contact_log()`, `save_contact_log()`

**Adapter status:**
- `FilesystemAwsCsmNewsletterStateAdapter` — exists, currently in use
- SQL/MOS adapter — **does not exist**

**Datum mutation port:** `AuthoritativeDatumDocumentMutationPort` exists in
`packages/ports/datum_store/contracts.py` but is designed for structured datum
documents with MSN ownership, not for service-tool JSON objects.

---

## C. Prerequisites for MOS Datum Upsert

Five items must exist before migration is safe:

1. **Schema definition** — `mycite.webapp.contact_log.v1` is not a MOS datum
   schema. A registered MOS datum schema must be created.
2. **Ownership model** — Which MSN ID owns domain contact logs? (FND portal
   instance, or a dedicated newsletter service principal?)
3. **Sandbox assignment** — Which sandbox hosts contact log datums?
4. **SQL adapter** — `SqliteMosAwsCsmNewsletterStateAdapter` implementing
   `AwsCsmNewsletterStatePort` does not exist.
5. **Migration path** — Existing filesystem contact logs must be bulk-imported
   before filesystem writes can be retired.

---

## D. Formal Disposition: DEFER

**Reasoning:**
- The implementation plan that introduced these routes (Newsletter-Subscribe-Pipeline
  2026-05-03) explicitly states filesystem is the canonical store for v1 and MOS
  migration is a future concern.
- All three endpoints are functioning correctly with atomic filesystem writes.
- No blocking urgency — no data loss or architectural blocker.
- The upstream MOS semantic gates (ownership, schema) are unresolved for v1.
- Premature migration before ownership model is defined risks non-canonical datum IDs.

**Before this migration can proceed, two prerequisite tasks must complete:**

1. **TASK-NEWSLETTER-MOS-SEMANTICS** (new, p3/exploration)  
   Define: contact log ownership model, MOS datum schema, sandbox assignment,
   canonical document ID convention.  
   Output: formal contract in `docs/contracts/`.

2. **TASK-NEWSLETTER-SQL-ADAPTER** (new, p3/implementation — after semantics)  
   Implement `SqliteMosAwsCsmNewsletterStateAdapter` supporting subscribe,
   unsubscribe, and dispatch_result mutations.  
   Output: new adapter in `packages/adapters/sql/`.

The three TODO comments may remain as-is until those prerequisite tasks complete.
