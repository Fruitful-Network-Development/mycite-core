"""Tests for MosDatumPayPalOrdersAdapter + MosDatumPayPalWebhookAdapter."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.fnd_paypal import (
    MosDatumPayPalOrdersAdapter,
    MosDatumPayPalWebhookAdapter,
    ORDERS_MAX_PER_DOMAIN,
    ORDERS_SCHEMA,
    WEBHOOK_SCHEMA,
)


class PayPalOrdersAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "mos.sqlite3"
        self.adapter = MosDatumPayPalOrdersAdapter(
            authority_db_file=self.db,
            tenant_id="tenant",
            msn_id="test-msn",
        )

    def test_load_empty_when_missing(self) -> None:
        self.assertEqual(self.adapter.load_orders(domain="ex.com"), [])

    def test_save_then_load_round_trip(self) -> None:
        orders = [
            {
                "event": "PAYMENT.CAPTURE.COMPLETED",
                "order_id": "order-001",
                "amount": "25.00",
                "currency_code": "USD",
                "status": "COMPLETED",
                "timestamp_ms": 1778640000000,
                "domain": "trappfamilyfarm.com",
            },
            {
                "event": "PAYMENT.CAPTURE.COMPLETED",
                "order_id": "order-002",
                "amount": "23.00",
                "currency_code": "USD",
                "status": "COMPLETED",
                "timestamp_ms": 1778640060000,
                "domain": "trappfamilyfarm.com",
            },
        ]
        self.adapter.save_orders(domain="trappfamilyfarm.com", orders=orders)
        loaded = self.adapter.load_orders(domain="trappfamilyfarm.com")
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["order_id"], "order-001")
        self.assertEqual(loaded[1]["amount"], "23.00")

    def test_save_caps_orders_per_domain(self) -> None:
        orders = [
            {"event": "x", "order_id": f"order-{i}", "amount": "1", "currency_code": "USD",
             "status": "OK", "timestamp_ms": i, "domain": "ex.com"}
            for i in range(ORDERS_MAX_PER_DOMAIN + 5)
        ]
        self.adapter.save_orders(domain="ex.com", orders=orders)
        loaded = self.adapter.load_orders(domain="ex.com", limit=ORDERS_MAX_PER_DOMAIN + 10)
        self.assertEqual(len(loaded), ORDERS_MAX_PER_DOMAIN)


class PayPalWebhookAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "mos.sqlite3"
        self.adapter = MosDatumPayPalWebhookAdapter(
            authority_db_file=self.db,
            tenant_id="tenant",
            msn_id="test-msn",
        )

    def test_load_returns_none_when_missing(self) -> None:
        self.assertIsNone(self.adapter.load_webhook(grantee_msn_id="some-msn"))

    def test_save_then_load_webhook(self) -> None:
        self.adapter.save_webhook(
            grantee_msn_id="3-2-3-17-77-1",
            webhook_url="https://example.com/paypal-webhook",
        )
        loaded = self.adapter.load_webhook(grantee_msn_id="3-2-3-17-77-1")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["schema"], WEBHOOK_SCHEMA)
        self.assertEqual(loaded["webhook_url"], "https://example.com/paypal-webhook")
        self.assertEqual(loaded["msn_id"], "3-2-3-17-77-1")

    def test_save_idempotent_on_same_value(self) -> None:
        # First save creates doc, second save with same value advances
        # the document_id (updated_at differs even when webhook_url is
        # identical because the header carries computed_at).
        self.adapter.save_webhook(
            grantee_msn_id="g1", webhook_url="https://a.example/wh",
        )
        first_doc = self.adapter._find_doc(grantee_msn_id="g1")  # type: ignore[attr-defined]
        assert first_doc is not None
        self.adapter.save_webhook(
            grantee_msn_id="g1", webhook_url="https://a.example/wh",
        )
        second_doc = self.adapter._find_doc(grantee_msn_id="g1")  # type: ignore[attr-defined]
        assert second_doc is not None
        # Different timestamps produce different version_hashes; both
        # docs persist as a single doc replaced atomically.
        self.assertEqual(
            second_doc.canonical_name, first_doc.canonical_name
        )


if __name__ == "__main__":
    unittest.main()
