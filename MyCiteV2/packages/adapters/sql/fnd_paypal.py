"""MOS-backed adapters for FND PayPal orders + webhook configuration.

Two datum families in the ``fnd_csm`` sandbox:

* **Orders ledger** (per-domain): one datum per domain
  (``fnd_paypal_orders_<domain_token>``) carrying up to N most-recent
  orders as repeating layer-1 rows. Schema:
  ``mycite.v2.datum.fnd.paypal.orders.v1``.

* **Webhook config** (per-grantee): one datum per grantee MSN
  (``fnd_paypal_webhook_<msn_id_token>``) carrying the webhook URL +
  metadata in header rows. Schema:
  ``mycite.v2.datum.fnd.paypal.webhook.v1``.

The legacy sources are:

* ``<private>/utilities/tools/paypal-csm/orders.ndjson`` — append-only
  NDJSON file with all orders across all domains.
* ``<private>/utilities/tools/fnd-csm/paypal-webhook.<msn>.json`` — one
  JSON file per grantee.

Migration scripts ingest the legacy sources into MOS; the runtime
``_build_paypal_extension_payload`` prefers MOS when present and falls back to the
filesystem otherwise.
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


ORDERS_SCHEMA = "mycite.v2.datum.fnd.paypal.orders.v1"
WEBHOOK_SCHEMA = "mycite.v2.datum.fnd.paypal.webhook.v1"
SANDBOX = FND_CSM_SANDBOX_TOKEN
DEFAULT_TENANT_ID = "fnd"
DEFAULT_MSN_ID = "3-2-3-17-77-1-6-4-1-4"
ORDERS_NAME_PREFIX = "fnd_paypal_orders_"
WEBHOOK_NAME_PREFIX = "fnd_paypal_webhook_"
ORDERS_MAX_PER_DOMAIN = 100


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _as_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _domain_token(domain: str) -> str:
    return _as_text(domain).lower().replace(".", "_").replace("-", "_")


def _msn_token(msn_id: str) -> str:
    return _as_text(msn_id).replace(".", "_").replace("-", "_")


def _orders_canonical_name(domain: str) -> str:
    return f"{ORDERS_NAME_PREFIX}{_domain_token(domain)}"


def _webhook_canonical_name(msn_id: str) -> str:
    return f"{WEBHOOK_NAME_PREFIX}{_msn_token(msn_id)}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _persist_doc(
    *,
    store: SqliteSystemDatumStoreAdapter,
    tenant_id: str,
    msn_id: str,
    prior_document_id: str | None,
    canonical_name: str,
    rows: list[AuthoritativeDatumDocumentRow],
) -> None:
    from MyCiteV2.packages.core.document_naming import format_canonical_document_id
    from MyCiteV2.packages.core.mss import compute_mss_hash

    document_name = f"{canonical_name}.json"
    relative_path = f"sandbox/fnd-csm/{document_name}"
    placeholder_id = format_canonical_document_id(
        prefix="lv",
        msn_id=msn_id,
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
        msn_id=msn_id,
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
        tenant_id=tenant_id,
        prior_document_id=prior_document_id,
        updated_document=final_document,
    )


class MosDatumPayPalOrdersAdapter:
    """Per-domain PayPal orders ledger."""

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

    def load_orders(self, *, domain: str, limit: int = 30) -> list[dict[str, Any]]:
        doc = self._find_doc(domain=domain)
        if doc is None:
            return []
        orders: list[dict[str, Any]] = []
        for row in doc.rows:
            if not row.datum_address.startswith("1-"):
                continue
            raw = row.raw
            magnitudes = (
                raw[1] if isinstance(raw, list) and len(raw) >= 2 and isinstance(raw[1], dict) else None
            )
            if magnitudes is None:
                continue
            orders.append({
                "event": _as_text(magnitudes.get("event")),
                "order_id": _as_text(magnitudes.get("order_id")),
                "amount": _as_text(magnitudes.get("amount")),
                "currency": _as_text(magnitudes.get("currency_code") or magnitudes.get("currency")),
                "status": _as_text(magnitudes.get("status")),
                "timestamp_ms": magnitudes.get("timestamp_ms"),
                "domain": _as_text(magnitudes.get("domain")) or domain,
            })
            if len(orders) >= limit:
                break
        return orders

    def save_orders(self, *, domain: str, orders: list[dict[str, Any]]) -> None:
        store = SqliteSystemDatumStoreAdapter(self._authority_db_file, allow_legacy_writes=True)
        existing = self._find_doc(domain=domain)
        prior_document_id = existing.document_id if existing is not None else None
        updated_at = _utc_now_iso()
        rows: list[AuthoritativeDatumDocumentRow] = [
            AuthoritativeDatumDocumentRow(datum_address="0-0-1", raw=ORDERS_SCHEMA),
            AuthoritativeDatumDocumentRow(datum_address="0-0-2", raw=_as_text(domain)),
            AuthoritativeDatumDocumentRow(datum_address="0-0-3", raw=updated_at),
            AuthoritativeDatumDocumentRow(datum_address="0-0-4", raw=len(orders)),
        ]
        for index, order in enumerate(orders[:ORDERS_MAX_PER_DOMAIN], start=1):
            address = f"1-0-{index}"
            magnitudes = {
                "event": _as_text(order.get("event")),
                "order_id": _as_text(order.get("order_id")),
                "amount": _as_text(order.get("amount")),
                "currency_code": _as_text(order.get("currency_code") or order.get("currency")),
                "status": _as_text(order.get("status")),
                "timestamp_ms": order.get("timestamp_ms"),
                "domain": _as_text(order.get("domain")) or _as_text(domain),
            }
            rows.append(
                AuthoritativeDatumDocumentRow(
                    datum_address=address,
                    raw=[[address, "~", "0-0-11"], magnitudes],
                )
            )
        _persist_doc(
            store=store,
            tenant_id=self._tenant_id,
            msn_id=self._msn_id,
            prior_document_id=prior_document_id,
            canonical_name=_orders_canonical_name(domain),
            rows=rows,
        )

    def _find_doc(self, *, domain: str) -> AuthoritativeDatumDocument | None:
        store = SqliteSystemDatumStoreAdapter(self._authority_db_file)
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=self._tenant_id)
        )
        canonical_name = _orders_canonical_name(domain)
        for doc in catalog.documents:
            if doc.canonical_name == canonical_name and f".{SANDBOX}." in doc.document_id:
                return doc
        return None


class MosDatumPayPalWebhookAdapter:
    """Per-grantee PayPal webhook config."""

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

    def load_webhook(self, *, grantee_msn_id: str) -> dict[str, Any] | None:
        doc = self._find_doc(grantee_msn_id=grantee_msn_id)
        if doc is None:
            return None
        header: dict[str, Any] = {}
        for row in doc.rows:
            if row.datum_address == "0-0-1":
                header["schema"] = _as_text(row.raw)
            elif row.datum_address == "0-0-2":
                header["msn_id"] = _as_text(row.raw)
            elif row.datum_address == "0-0-3":
                header["webhook_url"] = _as_text(row.raw)
            elif row.datum_address == "0-0-4":
                header["updated_at"] = _as_text(row.raw)
        return header

    def save_webhook(self, *, grantee_msn_id: str, webhook_url: str) -> None:
        store = SqliteSystemDatumStoreAdapter(self._authority_db_file, allow_legacy_writes=True)
        existing = self._find_doc(grantee_msn_id=grantee_msn_id)
        prior_document_id = existing.document_id if existing is not None else None
        rows: list[AuthoritativeDatumDocumentRow] = [
            AuthoritativeDatumDocumentRow(datum_address="0-0-1", raw=WEBHOOK_SCHEMA),
            AuthoritativeDatumDocumentRow(datum_address="0-0-2", raw=_as_text(grantee_msn_id)),
            AuthoritativeDatumDocumentRow(datum_address="0-0-3", raw=_as_text(webhook_url)),
            AuthoritativeDatumDocumentRow(datum_address="0-0-4", raw=_utc_now_iso()),
        ]
        _persist_doc(
            store=store,
            tenant_id=self._tenant_id,
            msn_id=self._msn_id,
            prior_document_id=prior_document_id,
            canonical_name=_webhook_canonical_name(grantee_msn_id),
            rows=rows,
        )

    def _find_doc(self, *, grantee_msn_id: str) -> AuthoritativeDatumDocument | None:
        store = SqliteSystemDatumStoreAdapter(self._authority_db_file)
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=self._tenant_id)
        )
        canonical_name = _webhook_canonical_name(grantee_msn_id)
        for doc in catalog.documents:
            if doc.canonical_name == canonical_name and f".{SANDBOX}." in doc.document_id:
                return doc
        return None


__all__ = [
    "MosDatumPayPalOrdersAdapter",
    "MosDatumPayPalWebhookAdapter",
    "ORDERS_MAX_PER_DOMAIN",
    "ORDERS_SCHEMA",
    "WEBHOOK_SCHEMA",
]
