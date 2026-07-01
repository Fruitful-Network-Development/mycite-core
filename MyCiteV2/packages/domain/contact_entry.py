"""Canonical per-grantee contact-entry normalizer.

ONE contact-row shape shared by every writer — website newsletter signup,
website connect-form submission, operator admin add/edit, and dashboard
add/edit. Every row carries the full field set; fields that don't apply to a
given source are present-but-empty ("hidden unused fields"), so the contact
store has no drift between writers.

Pure functions only (no project imports) so both the portal app and the datum
mutation runtime can import this without a circular dependency.

Row contract (envelope schema ``mycite.service_tool.newsletter.contact_log.v3``):

  identity   : email, name, first_name, middle_name, last_name, phone, zip,
               organization
  lifecycle  : subscribed (bool), source, signup_date, created_at, updated_at,
               subscribed_at, unsubscribed_at
  newsletter : send_count (int), last_newsletter_sent_at, last_message_id,
               last_error
  connect    : forward_status, subject, message, last_contacted_at
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

# String-valued canonical fields, in document order.
_STR_FIELDS: tuple[str, ...] = (
    # identity
    "email",
    "name",
    "first_name",
    "middle_name",
    "last_name",
    "phone",
    "zip",
    "organization",
    # lifecycle (string-valued)
    "source",
    "signup_date",
    "created_at",
    "updated_at",
    "subscribed_at",
    "unsubscribed_at",
    # set ONLY by the operator "unsubscribe all" bulk action, on rows that were
    # subscribed at that moment. "Resubscribe all" re-subscribes exactly the rows
    # carrying this marker (then clears it), so it undoes the temporary bulk
    # opt-out without resurrecting people who genuinely opted out on their own.
    "bulk_unsubscribed_at",
    # newsletter dispatch
    "last_newsletter_sent_at",
    "last_message_id",
    "last_error",
    # connect
    "forward_status",
    "subject",
    "message",
    "last_contacted_at",
)

# Full canonical field set (strings + the two typed fields).
CONTACT_ENTRY_FIELDS: tuple[str, ...] = (*_STR_FIELDS, "subscribed", "send_count")


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def split_legacy_name(value: object) -> tuple[str, str, str]:
    """Split a single display name into (first, middle, last)."""
    token = _text(value)
    if not token:
        return ("", "", "")
    parts = token.split()
    if len(parts) == 1:
        return (parts[0], "", "")
    if len(parts) == 2:
        return (parts[0], "", parts[1])
    return (parts[0], " ".join(parts[1:-1]), parts[-1])


def blank_contact_entry() -> dict[str, Any]:
    """A fully-populated empty row (all canonical fields at their default)."""
    row: dict[str, Any] = {field: "" for field in _STR_FIELDS}
    row["subscribed"] = False
    row["send_count"] = 0
    return row


def canonical_contact_entry(
    *,
    existing: Mapping[str, Any] | None = None,
    patch: Mapping[str, Any],
    now: str | None = None,
) -> dict[str, Any]:
    """Merge ``patch`` onto ``existing`` and return a fully-populated row.

    Rules:
      * Every canonical field is present in the result (default when absent).
      * A string patch value is applied only when non-empty — an empty string
        means "leave unchanged". This lets a caller send a whole form without
        wiping stored values (fixes the dashboard blank-field clobber).
      * ``subscribed`` is taken from the patch only when the key is present;
        otherwise the existing value is kept. So an edit/add never silently
        re-subscribes a contact who opted out — callers must set ``subscribed``
        explicitly to change it.
      * ``created_at`` is preserved from ``existing`` (set to ``now`` for a new
        row); ``updated_at`` is always stamped.
      * ``name`` and the first/middle/last parts are kept in sync.
      * ``subscribed_at`` is stamped the first time a row becomes subscribed.
    """
    stamp = now or _now_iso()
    base = dict(existing or {})
    row = blank_contact_entry()

    # 1. Carry existing values forward.
    for field in _STR_FIELDS:
        row[field] = _text(base.get(field))
    row["subscribed"] = bool(base.get("subscribed", False))
    row["send_count"] = int(base.get("send_count") or 0)

    # 2. Apply the patch (empty string = no change for string fields).
    for field in _STR_FIELDS:
        if field in patch:
            value = _text(patch.get(field))
            if value:
                row[field] = value
    if "subscribed" in patch:
        row["subscribed"] = bool(patch.get("subscribed"))
    if "send_count" in patch:
        try:
            row["send_count"] = int(patch.get("send_count") or 0)
        except (TypeError, ValueError):
            pass

    row["email"] = row["email"].lower()

    # 3. Keep the display name and the split parts in sync.
    parts = (row["first_name"], row["middle_name"], row["last_name"])
    composed = " ".join(part for part in parts if part)
    if composed:
        row["name"] = composed
    elif row["name"] and not any(parts):
        row["first_name"], row["middle_name"], row["last_name"] = split_legacy_name(
            row["name"]
        )

    # 4. Lifecycle timestamps.
    row["created_at"] = _text(base.get("created_at")) or stamp
    row["updated_at"] = stamp
    if row["subscribed"] and not row["subscribed_at"]:
        row["subscribed_at"] = stamp

    return row
