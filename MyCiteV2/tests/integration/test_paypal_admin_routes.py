"""Phase 14d.3 — PayPal CSV export route + payload-shape pins.

The PayPal extension card surfaces an "Export CSV" link that hits
``GET /__fnd/paypal/admin/export?domain=...``. The handler reads
orders from the MOS adapter (or the filesystem NDJSON fallback) and
returns ``text/csv`` with a Content-Disposition attachment header so
the browser downloads the file.

These tests pin:

  * Success path: GET with seeded NDJSON orders returns the right
    CSV header + one row per order.
  * Content-Disposition: filename includes the domain.
  * 400 on missing domain.
  * Domains with no orders still return a CSV with just the header.
  * Payload-shape: ``export_action`` carries the canonical URL +
    download attribute when a domain is set; empty when not.

(Inline edit-links per config field + client-side date/status
filters are deferred — the section-level Grantee Profile edit link
already exists, and filtering UI is its own JS scope.)
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app


def _seed_orders_ndjson(private_dir: Path, orders: list[dict]) -> None:
    path = private_dir / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(o) for o in orders), encoding="utf-8")


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class PayPalExportRouteTests(unittest.TestCase):
    def _build_client(self):
        tmp = Path(tempfile.mkdtemp(prefix="phase14d3_paypal_export_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client(), tmp

    def test_export_returns_csv_with_seeded_orders(self) -> None:
        client, tmp = self._build_client()
        _seed_orders_ndjson(
            tmp / "private",
            [
                {
                    "domain": "alpha.example.test",
                    "event": "captured",
                    "order_id": "ORD-1",
                    "status": "completed",
                    "amount": "10.00",
                    "currency_code": "USD",
                    "donor_email": "donor@example.test",
                    "donor_name": "Donor One",
                    "timestamp_ms": 1700000000000,
                },
                {
                    "domain": "alpha.example.test",
                    "event": "captured",
                    "order_id": "ORD-2",
                    "status": "completed",
                    "amount": "25.00",
                    "currency_code": "USD",
                    "donor_email": "donor2@example.test",
                    "donor_name": "Donor Two",
                    "timestamp_ms": 1700000100000,
                },
                # Different domain — should not appear in the export.
                {
                    "domain": "beta.example.test",
                    "event": "captured",
                    "order_id": "ORD-3",
                    "status": "completed",
                    "amount": "50.00",
                    "currency_code": "USD",
                    "timestamp_ms": 1700000200000,
                },
            ],
        )
        resp = client.get("/__fnd/paypal/admin/export?domain=alpha.example.test")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.headers["Content-Type"].startswith("text/csv"))
        body = resp.get_data(as_text=True)
        lines = body.strip().splitlines()
        self.assertEqual(len(lines), 3)  # header + 2 alpha rows
        self.assertIn("order_id", lines[0])
        self.assertIn("ORD-1", body)
        self.assertIn("ORD-2", body)
        self.assertNotIn("ORD-3", body)

    def test_export_attachment_filename_includes_domain(self) -> None:
        client, _ = self._build_client()
        resp = client.get("/__fnd/paypal/admin/export?domain=alpha.example.test")
        self.assertEqual(resp.status_code, 200)
        disposition = resp.headers.get("Content-Disposition", "")
        self.assertIn("paypal-orders-alpha.example.test.csv", disposition)

    def test_export_rejects_missing_domain(self) -> None:
        client, _ = self._build_client()
        resp = client.get("/__fnd/paypal/admin/export")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "missing_domain")

    def test_export_returns_header_only_when_no_orders(self) -> None:
        client, _ = self._build_client()
        resp = client.get("/__fnd/paypal/admin/export?domain=empty.example.test")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertEqual(len(body.strip().splitlines()), 1)  # header only


class PayPalExtensionPayloadExportActionTests(unittest.TestCase):
    """The paypal extension payload must carry an ``export_action`` so
    the JS renderer can wire the Export CSV download link.
    """

    def test_payload_has_export_action_when_domain_set(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.paypal import (
            _build_paypal_extension_payload,
        )

        out = _build_paypal_extension_payload(
            grantee={"paypal": {"webhook_url": "https://example.test/webhook"}},
            domain="alpha.example.test",
            private_dir=None,
        )
        action = out.get("export_action") or {}
        self.assertEqual(
            action.get("href"),
            "/__fnd/paypal/admin/export?domain=alpha.example.test",
        )
        self.assertEqual(action.get("download"), "paypal-orders-alpha.example.test.csv")

    def test_payload_drops_export_action_when_no_domain(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.paypal import (
            _build_paypal_extension_payload,
        )

        out = _build_paypal_extension_payload(
            grantee={"paypal": {"webhook_url": "https://example.test/webhook"}},
            domain="",
            private_dir=None,
        )
        # webhook_url is set, so the payload returns via the orders/webhook
        # branch — but export_action should still be empty without a domain.
        self.assertFalse(out.get("export_action") or {})


if __name__ == "__main__":
    unittest.main()
