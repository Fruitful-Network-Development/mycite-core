"""MOS-backed SES deliverability rollup adapter.

Reads the per-domain deliverability aggregate written by
:mod:`MyCiteV2.scripts.sync_ses_events` (which mirrors S3 SES event
NDJSON into a daily rollup). When no document exists yet — the common
case before the SES event sink Lambda is wired — :meth:`load_rollup`
returns the zero shape with ``available=False`` so the UI can render an
honest "not wired yet" state instead of pretending zeros are real.

Canonical name: ``fnd_email_deliverability_<domain_token>``
Schema:         ``mycite.v2.datum.fnd.email.deliverability.v1``

Document layout (typical FND tenant adapter):

* Layer 0 headers — ``schema``, ``domain``, ``computed_at``,
  ``send_count``, ``delivery_count``, ``bounce_count``,
  ``complaint_count``, ``open_count``, ``click_count``.
* Layer 1 repeating — one row per day with magnitudes
  ``date``, ``send``, ``delivery``, ``bounce``, ``complaint``, ``open``,
  ``click``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.adapters.sql._common import _as_int, _as_text, _domain_token, _rate
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.portal_shell import FND_CSM_SANDBOX_TOKEN

SCHEMA = "mycite.v2.datum.fnd.email.deliverability.v1"
SANDBOX = FND_CSM_SANDBOX_TOKEN
DEFAULT_TENANT_ID = "fnd"
DEFAULT_MSN_ID = "3-2-3-17-77-1-6-4-1-4"
CANONICAL_NAME_PREFIX = "fnd_email_deliverability_"

EVENT_KEYS = ("send", "delivery", "bounce", "complaint", "open", "click")

_HEADER_ADDRESSES = {
    "0-0-1": "schema",
    "0-0-2": "domain",
    "0-0-3": "computed_at",
    "0-0-4": "send_count",
    "0-0-5": "delivery_count",
    "0-0-6": "bounce_count",
    "0-0-7": "complaint_count",
    "0-0-8": "open_count",
    "0-0-9": "click_count",
}


def _canonical_name_for(domain: str) -> str:
    return f"{CANONICAL_NAME_PREFIX}{_domain_token(domain)}"


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty_rollup(domain: str, period: tuple[str, str] | None) -> dict[str, Any]:
    """Zero-shape rollup used when no MOS document exists. Marks
    ``available=False`` so the UI can render an honest empty state."""
    start = period[0] if period else ""
    end = period[1] if period else ""
    return {
        "schema": SCHEMA,
        "domain": domain,
        "available": False,
        "computed_at": "",
        "period": {"from": start, "to": end},
        "send_count": 0,
        "delivery_count": 0,
        "bounce_count": 0,
        "complaint_count": 0,
        "open_count": 0,
        "click_count": 0,
        "bounce_rate": 0.0,
        "complaint_rate": 0.0,
        "by_day": [],
    }


def _date_in_range(d: str, start: str, end: str) -> bool:
    """Half-open: [start, end). Empty bounds mean "no filter on that side"."""
    if start and d < start:
        return False
    if end and d >= end:
        return False
    return True


class MosDatumEmailDeliverabilityAdapter:
    """Read + write the per-domain SES deliverability rollup datum."""

    def __init__(
        self,
        *,
        authority_db_file: str | Path,
        tenant_id: str = DEFAULT_TENANT_ID,
        msn_id: str = DEFAULT_MSN_ID,
    ) -> None:
        self._authority_db_file = Path(authority_db_file)
        self._tenant_id = tenant_id
        self._msn_id = msn_id

    # ----- read -------------------------------------------------------

    def load_rollup(
        self,
        *,
        domain: str,
        period: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        """Return the deliverability rollup for ``domain`` over ``period``.

        ``period`` is a (from, to) tuple of ISO-date strings, half-open.
        When None, returns the full rollup. When no MOS document exists
        yet, returns the zero shape with ``available=False`` — callers
        should branch on that flag rather than checking for zero counts
        (a domain might legitimately have zero events in a period and
        we want to distinguish that from "no pipeline").
        """
        doc = self._find_doc(domain=domain)
        if doc is None:
            return _empty_rollup(domain, period)

        header = self._header_field_map(doc.rows)
        # Day-level rows
        by_day: list[dict[str, Any]] = []
        for row in doc.rows:
            if not row.datum_address.startswith("1-"):
                continue
            raw = row.raw
            magnitudes = (
                raw[1] if isinstance(raw, list) and len(raw) >= 2 and isinstance(raw[1], dict) else None
            )
            if magnitudes is None:
                continue
            entry = {"date": _as_text(magnitudes.get("date"))}
            for k in EVENT_KEYS:
                entry[k] = _as_int(magnitudes.get(k))
            by_day.append(entry)

        # Period filter
        start = period[0] if period else ""
        end = period[1] if period else ""
        filtered = [d for d in by_day if _date_in_range(d["date"], start, end)]

        # If a period was supplied, totals come from the filtered slice;
        # otherwise use header totals (which span everything ingested).
        if period:
            totals = {k: sum(d[k] for d in filtered) for k in EVENT_KEYS}
        else:
            totals = {
                "send":      _as_int(header.get("send_count")),
                "delivery":  _as_int(header.get("delivery_count")),
                "bounce":    _as_int(header.get("bounce_count")),
                "complaint": _as_int(header.get("complaint_count")),
                "open":      _as_int(header.get("open_count")),
                "click":     _as_int(header.get("click_count")),
            }

        send = totals["send"]
        return {
            "schema": SCHEMA,
            "domain": header.get("domain", domain),
            "available": True,
            "computed_at": header.get("computed_at", ""),
            "period": {"from": start, "to": end},
            "send_count":      send,
            "delivery_count":  totals["delivery"],
            "bounce_count":    totals["bounce"],
            "complaint_count": totals["complaint"],
            "open_count":      totals["open"],
            "click_count":     totals["click"],
            "bounce_rate":     _rate(totals["bounce"],    send),
            "complaint_rate":  _rate(totals["complaint"], send),
            "by_day": filtered,
        }

    # ----- write ------------------------------------------------------

    def save_rollup(
        self,
        *,
        domain: str,
        by_day: list[dict[str, Any]],
    ) -> None:
        """Persist the rollup. ``by_day`` is a list of dicts with keys
        ``date`` + every key in :data:`EVENT_KEYS`. Header totals are
        computed from ``by_day`` so they always agree with the rows."""
        from MyCiteV2.packages.core.document_naming import format_canonical_document_id
        from MyCiteV2.packages.core.mss import compute_mss_hash

        store = SqliteSystemDatumStoreAdapter(self._authority_db_file, allow_legacy_writes=False)
        existing = self._find_doc(domain=domain)
        prior_document_id = existing.document_id if existing is not None else None
        canonical_name = _canonical_name_for(domain)
        document_name = f"{canonical_name}.json"
        relative_path = f"sandbox/fnd-csm/{document_name}"
        computed_at = _utc_now_iso()

        # Dedupe by date FIRST (last write wins) so header totals
        # always agree with the per-day rows we actually persist.
        seen: dict[str, dict[str, Any]] = {}
        for d in by_day:
            key = _as_text(d.get("date"))
            if not key:
                continue
            seen[key] = d
        totals = {k: sum(_as_int(d.get(k)) for d in seen.values()) for k in EVENT_KEYS}

        rows: list[AuthoritativeDatumDocumentRow] = [
            AuthoritativeDatumDocumentRow(datum_address="0-0-1", raw=SCHEMA),
            AuthoritativeDatumDocumentRow(datum_address="0-0-2", raw=_as_text(domain)),
            AuthoritativeDatumDocumentRow(datum_address="0-0-3", raw=computed_at),
            AuthoritativeDatumDocumentRow(datum_address="0-0-4", raw=int(totals["send"])),
            AuthoritativeDatumDocumentRow(datum_address="0-0-5", raw=int(totals["delivery"])),
            AuthoritativeDatumDocumentRow(datum_address="0-0-6", raw=int(totals["bounce"])),
            AuthoritativeDatumDocumentRow(datum_address="0-0-7", raw=int(totals["complaint"])),
            AuthoritativeDatumDocumentRow(datum_address="0-0-8", raw=int(totals["open"])),
            AuthoritativeDatumDocumentRow(datum_address="0-0-9", raw=int(totals["click"])),
        ]
        for index, key in enumerate(sorted(seen.keys()), start=1):
            d = seen[key]
            address = f"1-0-{index}"
            rows.append(
                AuthoritativeDatumDocumentRow(
                    datum_address=address,
                    raw=[
                        [address, "~", "0-0-11"],
                        {
                            "date": _as_text(d.get("date")),
                            **{k: _as_int(d.get(k)) for k in EVENT_KEYS},
                        },
                    ],
                )
            )

        placeholder_id = format_canonical_document_id(
            prefix="lv",
            msn_id=self._msn_id,
            sandbox=SANDBOX,
            name=canonical_name,
            version_hash="0" * 64,
        )
        candidate = AuthoritativeDatumDocument(
            document_id=placeholder_id,
            source_kind="sandbox_source",
            document_name=document_name,
            relative_path=relative_path,
            canonical_name=canonical_name,
            tool_id=SANDBOX,
            is_anchor=False,
            rows=tuple(rows),
        )
        identity = compute_mss_hash(candidate)
        real_hash = identity["version_hash"]
        if real_hash.startswith("sha256:"):
            real_hash = real_hash[len("sha256:") :]
        real_id = format_canonical_document_id(
            prefix="lv",
            msn_id=self._msn_id,
            sandbox=SANDBOX,
            name=canonical_name,
            version_hash=real_hash,
        )
        final_document = AuthoritativeDatumDocument(
            document_id=real_id,
            source_kind="sandbox_source",
            document_name=document_name,
            relative_path=relative_path,
            canonical_name=canonical_name,
            tool_id=SANDBOX,
            is_anchor=False,
            rows=tuple(rows),
        )
        store.replace_single_document_efficient(
            tenant_id=self._tenant_id,
            prior_document_id=prior_document_id,
            updated_document=final_document,
        )

    # ----- internals --------------------------------------------------

    def _find_doc(self, *, domain: str) -> AuthoritativeDatumDocument | None:
        store = SqliteSystemDatumStoreAdapter(self._authority_db_file)
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=self._tenant_id)
        )
        canonical_name = _canonical_name_for(domain)
        for doc in catalog.documents:
            if doc.canonical_name == canonical_name and f".{SANDBOX}." in doc.document_id:
                return doc
        return None

    @staticmethod
    def _header_field_map(
        rows: tuple[AuthoritativeDatumDocumentRow, ...],
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for row in rows:
            field = _HEADER_ADDRESSES.get(row.datum_address)
            if field:
                out[field] = row.raw
        return out
