"""PayPal management surface: scoped admin config/update, grantee-save scope,
single-store export, and the webhook reconciler.

PayPal HTTP calls are patched at the app helper boundary so the suite stays
offline.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app
    from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA

DOMAIN = "paypal.example.test"
APP = "MyCiteV2.instances._shared.portal_host.app"


def _seed_grantee(grantee_dir: Path, *, msn: str, domain: str, paypal: dict | None) -> None:
    grantee_dir.mkdir(parents=True, exist_ok=True)
    profile: dict = {
        "schema": GRANTEE_PROFILE_SCHEMA,
        "msn_id": msn,
        "label": msn,
        "short_name": msn,
        "domains": [domain],
        "users": [],
    }
    if paypal is not None:
        profile["paypal"] = paypal
    (grantee_dir / f"grantee.fnd-msn.{msn}.json").write_text(
        json.dumps(profile), encoding="utf-8"
    )


def _seed_paypal_domain(private_dir: Path, domain: str) -> None:
    tool_dir = private_dir / "utilities" / "tools" / "paypal-csm"
    tool_dir.mkdir(parents=True, exist_ok=True)
    (tool_dir / "paypal-csm.alpha.json").write_text(
        json.dumps(
            {
                "domain": domain,
                "tenant_ref": "1",
                "environment": "sandbox",
                "brand_name": "Alpha",
                "checkout_context": {"currency_code": "USD"},
                "donation_defaults": {},
            }
        ),
        encoding="utf-8",
    )
    (tool_dir / "tenants").mkdir(parents=True, exist_ok=True)
    (tool_dir / "tenants" / "1.json").write_text(
        json.dumps({"credentials_ref": "set-locally-in-state-or-runtime"}),
        encoding="utf-8",
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class PaypalManagementTests(unittest.TestCase):
    def _build_client(self, *, paypal: dict | None):
        tmp = Path(tempfile.mkdtemp(prefix="paypal_mgmt_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        _seed_grantee(
            tmp / "private" / "utilities" / "tools" / "fnd-csm",
            msn="alpha",
            domain=DOMAIN,
            paypal=paypal,
        )
        _seed_paypal_domain(tmp / "private", DOMAIN)
        authority_db = tmp / "authority.sqlite3"
        authority_db.touch()
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="fruitfulnetworkdevelopment.com",
            webapps_root=tmp / "webapps",
            authority_db_file=authority_db,
        )
        return create_app(config).test_client(), tmp

    # ---- admin config / update -------------------------------------------

    def test_config_masks_secret(self) -> None:
        client, _ = self._build_client(
            paypal={"client_id": "id123", "client_secret": "secretXYZ9", "environment": "live"}
        )
        resp = client.get("/__fnd/paypal/admin/config?grantee=alpha")
        self.assertEqual(resp.status_code, 200)
        pp = resp.get_json()["paypal"]
        self.assertNotIn("client_secret", pp)
        self.assertEqual(pp["client_id"], "id123")
        self.assertEqual(pp["environment"], "live")
        self.assertTrue(pp["has_secret"])
        self.assertEqual(pp["secret_tail"], "XYZ9")

    def test_update_writes_and_rewires(self) -> None:
        client, _ = self._build_client(paypal=None)
        resp = client.post(
            "/__fnd/paypal/admin/update?grantee=alpha",
            data=json.dumps(
                {
                    "environment": "live",
                    "client_id": "newid",
                    "client_secret": "supersecret42",
                    "webhook_id": "WH-1",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        # Read back: the config GET reflects the write (fresh per request).
        cfg = client.get("/__fnd/paypal/admin/config?grantee=alpha").get_json()["paypal"]
        self.assertEqual(cfg["client_id"], "newid")
        self.assertEqual(cfg["environment"], "live")
        self.assertEqual(cfg["webhook_id"], "WH-1")
        self.assertTrue(cfg["has_secret"])

    def test_update_rejects_bad_environment(self) -> None:
        client, _ = self._build_client(paypal=None)
        resp = client.post(
            "/__fnd/paypal/admin/update?grantee=alpha",
            data=json.dumps({"environment": "production-ish", "client_id": "x", "client_secret": "y"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_environment")

    def test_update_empty_secret_leaves_unchanged(self) -> None:
        client, _ = self._build_client(
            paypal={"client_id": "oldid", "client_secret": "keepme1234", "environment": "sandbox"}
        )
        resp = client.post(
            "/__fnd/paypal/admin/update?grantee=alpha",
            data=json.dumps({"environment": "sandbox", "client_id": "changedid", "client_secret": ""}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        cfg = client.get("/__fnd/paypal/admin/config?grantee=alpha").get_json()["paypal"]
        self.assertEqual(cfg["client_id"], "changedid")
        self.assertTrue(cfg["has_secret"])
        self.assertEqual(cfg["secret_tail"], "1234")  # secret preserved

    # ---- grantee/save scope ----------------------------------------------

    def test_grantee_save_blocks_foreign_grantee(self) -> None:
        client, _ = self._build_client(paypal=None)
        # Caller is grantee "alpha" (header); they may not edit grantee "beta".
        resp = client.post(
            "/__fnd/grantee/save",
            data=json.dumps({"msn_id": "beta", "fields": {"label": "Hijacked"}}),
            content_type="application/json",
            headers={"X-Auth-Request-Grantee": "alpha"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.get_json()["error"], "grantee_not_owned")

    # ---- single-store export ---------------------------------------------

    def test_export_reads_order_log(self) -> None:
        client, tmp = self._build_client(paypal=None)
        log = tmp / "private" / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"
        log.write_text(
            json.dumps(
                {
                    "event": "capture_order",
                    "order_id": "O1",
                    "capture_id": "CAP1",
                    "domain": DOMAIN,
                    "amount": "25.00",
                    "currency_code": "USD",
                    "status": "COMPLETED",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        resp = client.get(f"/__fnd/paypal/admin/export?domain={DOMAIN}")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        # The order log row is reflected in the export (single store, no MOS).
        self.assertIn("O1", body)
        self.assertIn("25.00", body)
        self.assertIn(DOMAIN, body)

    # ---- webhook ----------------------------------------------------------

    def test_webhook_requires_webhook_id(self) -> None:
        client, _ = self._build_client(
            paypal={"client_id": "id", "client_secret": "sec", "environment": "sandbox"}
        )
        resp = client.post(
            "/__fnd/paypal/webhook",
            data=json.dumps({"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {}}),
            content_type="application/json",
            base_url=f"http://{DOMAIN}",
        )
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.get_json()["error"], "webhook_id_not_set")

    def test_webhook_signature_failure_rejected(self) -> None:
        client, _ = self._build_client(
            paypal={"client_id": "id", "client_secret": "sec", "environment": "sandbox", "webhook_id": "WH-1"}
        )
        with patch(f"{APP}._get_paypal_access_token", return_value="tok"), patch(
            f"{APP}._verify_paypal_webhook_signature", return_value=False
        ):
            resp = client.post(
                "/__fnd/paypal/webhook",
                data=json.dumps({"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"id": "CAP9"}}),
                content_type="application/json",
                base_url=f"http://{DOMAIN}",
            )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "signature_verification_failed")

    def test_webhook_capture_completed_idempotent(self) -> None:
        client, tmp = self._build_client(
            paypal={"client_id": "id", "client_secret": "sec", "environment": "sandbox", "webhook_id": "WH-1"}
        )
        event = {
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {
                "id": "CAPABC",
                "status": "COMPLETED",
                "amount": {"value": "40.00", "currency_code": "USD"},
                "supplementary_data": {"related_ids": {"order_id": "ORD7"}},
            },
        }
        log = tmp / "private" / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"
        with patch(f"{APP}._get_paypal_access_token", return_value="tok"), patch(
            f"{APP}._verify_paypal_webhook_signature", return_value=True
        ):
            for _ in range(2):  # deliver twice → idempotent
                resp = client.post(
                    "/__fnd/paypal/webhook",
                    data=json.dumps(event),
                    content_type="application/json",
                    base_url=f"http://{DOMAIN}",
                )
                self.assertEqual(resp.status_code, 200)
        rows = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
        captures = [r for r in rows if r.get("capture_id") == "CAPABC"]
        self.assertEqual(len(captures), 1)
        self.assertEqual(captures[0]["amount"], "40.00")
        self.assertEqual(captures[0]["order_id"], "ORD7")


if __name__ == "__main__":
    unittest.main()
