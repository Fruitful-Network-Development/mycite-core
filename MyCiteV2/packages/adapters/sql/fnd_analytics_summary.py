"""MOS-backed analytics summary adapter.

Stores a rolling-window aggregate (page_view / form_submit / ops_probe /
other counts) plus the 20 most recent events per domain as a datum
document in the ``fnd_csm`` sandbox. The legacy Analytics tab globs
``<webapps>/clients/<domain>/analytics/events/*.ndjson`` on every
request — this adapter caches the aggregate in MOS so reads are
constant-time. A periodic sync job
(:mod:`MyCiteV2.scripts.sync_fnd_analytics_summary`) refreshes the
datum from the NDJSON sources.

Canonical name: ``fnd_analytics_summary_<domain_token>``
Schema:         ``mycite.v2.datum.fnd.analytics.summary.v1``

Document layout:

* Layer 0 headers — ``schema``, ``domain``, ``window_months``,
  ``computed_at``, ``page_view_count``, ``form_submit_count``,
  ``ops_probe_count``, ``other_count``.
* Layer 1 repeating — one row per recent event (up to 20), with
  magnitudes ``event_type``, ``path``, ``timestamp``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.portal_shell import FND_CSM_SANDBOX_TOKEN


SCHEMA = "mycite.v2.datum.fnd.analytics.summary.v1"
SANDBOX = FND_CSM_SANDBOX_TOKEN
DEFAULT_TENANT_ID = "fnd"
DEFAULT_MSN_ID = "3-2-3-17-77-1-6-4-1-4"
CANONICAL_NAME_PREFIX = "fnd_analytics_summary_"
MAX_RECENT_EVENTS = 20


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _as_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _domain_token(domain: str) -> str:
    return _as_text(domain).lower().replace(".", "_").replace("-", "_")


def _canonical_name_for(domain: str) -> str:
    return f"{CANONICAL_NAME_PREFIX}{_domain_token(domain)}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class MosDatumAnalyticsSummaryAdapter:
    """Read + write the per-domain analytics summary datum."""

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

    def load_summary(self, *, domain: str) -> dict[str, Any] | None:
        """Return the latest aggregate for ``domain`` or ``None``."""
        doc = self._find_doc(domain=domain)
        if doc is None:
            return None
        header = self._header_field_map(doc.rows)
        recent: list[dict[str, Any]] = []
        for row in doc.rows:
            if not row.datum_address.startswith("1-"):
                continue
            raw = row.raw
            magnitudes = (
                raw[1] if isinstance(raw, list) and len(raw) >= 2 and isinstance(raw[1], dict) else None
            )
            if magnitudes is None:
                continue
            recent.append({
                "event_type": _as_text(magnitudes.get("event_type")),
                "path": _as_text(magnitudes.get("path")) or "—",
                "timestamp": _as_text(magnitudes.get("timestamp")),
            })
        return {
            "schema": SCHEMA,
            "domain": header.get("domain", domain),
            "window_months": _as_int(header.get("window_months")),
            "computed_at": header.get("computed_at", ""),
            "summary": {
                "page_view": _as_int(header.get("page_view_count")),
                "form_submit": _as_int(header.get("form_submit_count")),
                "ops_probe": _as_int(header.get("ops_probe_count")),
                "other": _as_int(header.get("other_count")),
            },
            "recent_events": recent,
        }

    def save_summary(
        self,
        *,
        domain: str,
        window_months: int,
        counts: dict[str, int],
        recent_events: list[dict[str, Any]],
    ) -> None:
        from MyCiteV2.packages.core.document_naming import format_canonical_document_id
        from MyCiteV2.packages.core.mss import compute_mss_hash

        store = SqliteSystemDatumStoreAdapter(self._authority_db_file, allow_legacy_writes=True)
        existing = self._find_doc(domain=domain)
        prior_document_id = existing.document_id if existing is not None else None
        canonical_name = _canonical_name_for(domain)
        document_name = f"{canonical_name}.json"
        relative_path = f"sandbox/fnd-csm/{document_name}"
        computed_at = _utc_now_iso()

        rows: list[AuthoritativeDatumDocumentRow] = [
            AuthoritativeDatumDocumentRow(datum_address="0-0-1", raw=SCHEMA),
            AuthoritativeDatumDocumentRow(datum_address="0-0-2", raw=_as_text(domain)),
            AuthoritativeDatumDocumentRow(datum_address="0-0-3", raw=int(window_months)),
            AuthoritativeDatumDocumentRow(datum_address="0-0-4", raw=computed_at),
            AuthoritativeDatumDocumentRow(
                datum_address="0-0-5", raw=int(counts.get("page_view", 0))
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="0-0-6", raw=int(counts.get("form_submit", 0))
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="0-0-7", raw=int(counts.get("ops_probe", 0))
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="0-0-8", raw=int(counts.get("other", 0))
            ),
        ]
        for index, event in enumerate(recent_events[:MAX_RECENT_EVENTS], start=1):
            address = f"1-0-{index}"
            rows.append(
                AuthoritativeDatumDocumentRow(
                    datum_address=address,
                    raw=[
                        [address, "~", "0-0-11"],
                        {
                            "event_type": _as_text(event.get("event_type")),
                            "path": _as_text(event.get("path")),
                            "timestamp": _as_text(event.get("timestamp")),
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
    def _header_field_map(rows: tuple[AuthoritativeDatumDocumentRow, ...]) -> dict[str, Any]:
        mapping = {
            "0-0-1": "schema",
            "0-0-2": "domain",
            "0-0-3": "window_months",
            "0-0-4": "computed_at",
            "0-0-5": "page_view_count",
            "0-0-6": "form_submit_count",
            "0-0-7": "ops_probe_count",
            "0-0-8": "other_count",
        }
        out: dict[str, Any] = {}
        for row in rows:
            field = mapping.get(row.datum_address)
            if field is not None:
                out[field] = row.raw
        return out


__all__ = ["MAX_RECENT_EVENTS", "MosDatumAnalyticsSummaryAdapter", "SCHEMA"]
