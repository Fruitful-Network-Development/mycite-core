# Contract Update Protocol

This document describes the **revisioned update protocol** for contract compact arrays when one portal updates or adds datums and the other needs to be informed. Update evidence for **external** updates is carried via the request log; the actual contract state remains in the contract file.

See also: [AGRO_ERP_INTENTION.md](AGRO_ERP_INTENTION.md), [CONTRACT_COMPACT_INDEX.md](CONTRACT_COMPACT_INDEX.md), [REQUEST_LOG_V1.md](REQUEST_LOG_V1.md).

---

## Principles

- The **contract file** is the authoritative state. The request log carries **update evidence** (who changed what, when, and which revision), not the full state.
- Updates are **revisioned**: each snapshot or patch has a `revision`; messages reference `from_revision` and `to_revision`.
- **request_log** is used only when an update is **external** (e.g. TFF receives an update from FND, or sends one to FND). Local-only changes do not go to the request log.

---

## Update operations (intended)

| Operation | Description |
|-----------|-------------|
| `replace_snapshot` | Replace the compact array with a new compiled snapshot. |
| `add_entry` | Add one or more entries (by datum path). |
| `update_entry` | Update metadata or row for an existing datum path. |
| `remove_entry` | Remove one or more entries by datum path. |
| `recompile` | Recompile from owner_selected_refs / anthology and replace. |
| `acknowledge_revision` | Receiver acknowledges receipt of a revision. |

---

## Update message shape

Each update message should carry at least:

| Field | Description |
|-------|-------------|
| `contract_id` | Contract being updated. |
| `from_revision` | Revision before this update. |
| `to_revision` | Revision after this update. |
| `changed_paths` | List of canonical datum paths affected. |
| `change_type` | One of the operations above. |
| `source_msn_id` | MSN that produced the update. |
| `target_msn_id` | MSN that should apply or acknowledge. |
| `ts_unix_ms` | Timestamp of the update. |

Optional: `payload` (e.g. new snapshot or patch), `details` (operation-specific).

---

## When to use request_log

- **Do** append a request-log event when:
  - This portal **sends** an update to another portal (e.g. TFF pushes a compact-array update to FND).
  - This portal **receives** an update from another portal (e.g. TFF receives a compact-array update from FND).
  - This portal **acknowledges** a revision to the counterparty.
- **Do not** use request_log for:
  - Purely local contract edits (only this portal’s state changed).
  - Local tool CRUD (e.g. AGRO-ERP product-type creates). Use the **local audit log** (`portal.services.local_audit_log.append_audit_event`) instead. See AGRO_ERP_INTENTION.md and HOSTED_SESSIONS.md.

---

## Contract schema extensions (optional)

To support the protocol and relationship modes without breaking existing contracts, the contract payload may gain **optional** fields:

- `relationship_mode`: `unilateral_local` | `mirrored_shared` | `negotiated_shared`
- `access_mode`: `public` | `contract` | `private`
- `sync_mode`: `none` | `pull_refresh` | `push_notified` | `negotiated`
- `revision`: monotonic integer for the current compact-array snapshot

Existing contracts that omit these fields remain valid; defaults can be inferred (e.g. `relationship_mode` default from presence of counterparty_mss).

---

## Implementation

- **Local PATCH** (`PATCH /portal/api/contracts/<contract_id>`): When `owner_mss` or `owner_selected_refs` change, the API bumps `compact_index_revision` and sets `compact_index_compiled_at_unix_ms`. No request_log entry (local-only).
- **Apply external update** (`POST /portal/api/contracts/<contract_id>/compact-array/apply-update`): Body must include `from_revision`, `to_revision`, `change_type`, `source_msn_id`, `target_msn_id`, and optionally `ts_unix_ms`, `payload` (e.g. `counterparty_mss`). Validates `from_revision` matches stored revision; applies payload; persists; appends a `compact_array.update_applied` event to the request_log so the update is recorded for external/audit purposes.
