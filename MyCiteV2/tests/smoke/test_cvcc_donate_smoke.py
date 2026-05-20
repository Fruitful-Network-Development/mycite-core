"""CVCC PayPal sandbox donation preservation smoke (Phase 13d.2).

Boots a tempdir-backed FND portal on a free local port, seeds a paypal-csm
domain profile + tenant config keyed to ``127.0.0.1`` (the host the
chromium browser will actually request), registers a test-only route
that serves a minimal ``donate.html`` fixture, then drives a full
create-order → capture-order round-trip with PayPal mocked at the
``_create_paypal_order`` / ``_capture_paypal_order`` boundary.

This is the closest a CI-runnable smoke can get to the real
production flow at https://cuyahogavalleycountrysideconservancy.org/donate
without driving real PayPal sandbox traffic. No production HTTP is
generated; PayPal is never hit.

Runtime
=======
Requires playwright + chromium-headless-shell. See
``test_phase12h_browser_smoke.py`` for install commands.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None
FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None
WERKZEUG_AVAILABLE = importlib.util.find_spec("werkzeug") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app


# Same rationale as the TFF smoke: Chromium refuses to override the Host
# header, so the smoke uses 127.0.0.1 as the "domain" and seeds the
# paypal-csm profile accordingly.
_CVCC_DOMAIN = "127.0.0.1"

# The route handler reads tenant credentials from os.environ. The smoke
# sets these via @patch.dict so we don't pollute the real env.
_FAKE_CLIENT_ID = "FAKE_SANDBOX_CLIENT_ID"
_FAKE_CLIENT_SECRET = "FAKE_SANDBOX_CLIENT_SECRET"

_DONATE_HTML = """\
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>CVCC Donate Smoke</title></head>
<body>
  <h1>Donate</h1>
  <form id="donate">
    <input type="text" name="amount" value="5.00">
    <input type="text" name="donor_name" value="Test Donor">
    <input type="email" name="donor_email" value="donor@example.test">
    <input type="text" name="designation" value="general">
    <button type="submit">Donate</button>
  </form>
  <pre id="create_result"></pre>
  <pre id="capture_result"></pre>
  <script>
    document.getElementById("donate").addEventListener("submit", function (e) {
      e.preventDefault();
      var form = e.target;
      var body = {
        amount: form.amount.value,
        donor_name: form.donor_name.value,
        donor_email: form.donor_email.value,
        designation: form.designation.value
      };
      fetch("/__fnd/paypal/create-order", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body)
      })
        .then(function (r) { return r.json().then(function (j) { return {status: r.status, body: j}; }); })
        .then(function (out) {
          document.getElementById("create_result").textContent = JSON.stringify(out);
          if (out.body && out.body.order_id) {
            return fetch("/__fnd/paypal/capture-order", {
              method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({order_id: out.body.order_id})
            })
              .then(function (r) { return r.json().then(function (j) { return {status: r.status, body: j}; }); })
              .then(function (cap) {
                document.getElementById("capture_result").textContent = JSON.stringify(cap);
              });
          }
        });
    });
  </script>
</body></html>
"""


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _seed_paypal_csm_profile(private_dir: Path) -> None:
    """Seed paypal-csm.<domain>.json + tenants/1.json under private_dir.

    The route handler reads both at request time via _load_domain_profile +
    _load_tenant_config. Without them the route returns
    domain_profile_not_found / tenant_config_not_found.
    """
    tool_dir = private_dir / "utilities" / "tools" / "paypal-csm"
    tool_dir.mkdir(parents=True, exist_ok=True)
    (tool_dir / "paypal-csm.cvcc.json").write_text(
        json.dumps(
            {
                "domain": _CVCC_DOMAIN,
                "brand_name": "CVCC (test)",
                "environment": "sandbox",
                "tenant_ref": "1",
                "checkout_context": {
                    "return_url": "https://example.test/donate-return",
                    "cancel_url": "https://example.test/donate-cancel",
                    "currency_code": "USD",
                },
                "donation_defaults": {
                    "custom_id_prefix": "cvcc-test-donation",
                    "item_description": "Test donation",
                },
            }
        ),
        encoding="utf-8",
    )
    tenants_dir = tool_dir / "tenants"
    tenants_dir.mkdir(parents=True, exist_ok=True)
    # credentials_ref="1" means _resolve_paypal_credentials reads from
    # PAYPAL_CLIENT_ID + PAYPAL_CLIENT_SECRET (the unsuffixed env vars).
    (tenants_dir / "1.json").write_text(
        json.dumps({"credentials_ref": "1"}),
        encoding="utf-8",
    )


@unittest.skipUnless(
    PLAYWRIGHT_AVAILABLE and FLASK_AVAILABLE and WERKZEUG_AVAILABLE,
    "Browser smoke requires playwright + flask + werkzeug in the venv "
    "(playwright install chromium also required).",
)
class CvccDonateSmokeTests(unittest.TestCase):
    def _boot_portal(self) -> tuple:
        tmp = Path(tempfile.mkdtemp(prefix="cvcc_donate_smoke_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        _seed_paypal_csm_profile(tmp / "private")
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain=_CVCC_DOMAIN,
            webapps_root=tmp / "webapps",
        )
        app = create_app(config)

        from flask import Response

        @app.route("/__test/donate.html")
        def serve_donate_fixture():  # pragma: no cover - trivial
            return Response(_DONATE_HTML, mimetype="text/html")

        port = _free_port()
        from werkzeug.serving import make_server

        server = make_server("127.0.0.1", port, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.4)
        return server, thread, f"http://127.0.0.1:{port}", tmp

    def test_donate_form_round_trips_create_and_capture(self) -> None:
        from playwright.sync_api import sync_playwright

        # Mock the PayPal API helpers. _get_paypal_access_token is the
        # OAuth-token fetch; _create_paypal_order and _capture_paypal_order
        # are the create + capture POSTs (extracted in commit 08f8fe1).
        # All three are module-level functions in app.py — same patch
        # surface as Phase 13b's mockability tests.
        create_call_log: list[dict] = []
        capture_call_log: list[dict] = []

        def fake_token(*args, **kwargs) -> str:
            return "FAKE_TOKEN"

        def fake_create(*, access_token, base_url, body):
            create_call_log.append({"access_token": access_token, "base_url": base_url, "body": body})
            return {
                "id": "FAKE_ORDER_001",
                "status": "CREATED",
                "links": [{"rel": "approve", "href": "https://example.test/approve"}],
            }

        def fake_capture(*, access_token, base_url, order_id):
            capture_call_log.append({"access_token": access_token, "base_url": base_url, "order_id": order_id})
            return {
                "id": order_id,
                "status": "COMPLETED",
                "purchase_units": [{
                    "payments": {"captures": [{
                        "id": "FAKE_CAPTURE_001",
                        "amount": {"value": "5.00", "currency_code": "USD"},
                    }]},
                }],
            }

        server, thread, base, tmp = self._boot_portal()
        try:
            with patch.dict(
                "os.environ",
                {"PAYPAL_CLIENT_ID": _FAKE_CLIENT_ID, "PAYPAL_CLIENT_SECRET": _FAKE_CLIENT_SECRET},
            ), patch(
                "MyCiteV2.instances._shared.portal_host.app._get_paypal_access_token",
                side_effect=fake_token,
            ), patch(
                "MyCiteV2.instances._shared.portal_host.app._create_paypal_order",
                side_effect=fake_create,
            ), patch(
                "MyCiteV2.instances._shared.portal_host.app._capture_paypal_order",
                side_effect=fake_capture,
            ):
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    ctx = browser.new_context()
                    page = ctx.new_page()
                    page.goto(f"{base}/__test/donate.html", wait_until="networkidle", timeout=15000)

                    # Submit the form → fires both /create-order and
                    # /capture-order.
                    with page.expect_response(
                        lambda r: "/__fnd/paypal/capture-order" in r.url
                        and r.request.method == "POST",
                        timeout=10000,
                    ) as cap_info:
                        page.click("button[type=submit]")
                    capture_resp = cap_info.value
                    self.assertEqual(capture_resp.status, 200)
                    capture_body = capture_resp.json()
                    self.assertTrue(capture_body.get("ok"))
                    self.assertEqual(capture_body.get("status"), "COMPLETED")
                    self.assertEqual(capture_body.get("capture_id"), "FAKE_CAPTURE_001")

                    browser.close()

            # PayPal mocks were called exactly once each, in order.
            self.assertEqual(len(create_call_log), 1, f"create calls: {create_call_log!r}")
            self.assertEqual(create_call_log[0]["base_url"], "https://api-m.sandbox.paypal.com")
            self.assertEqual(create_call_log[0]["access_token"], "FAKE_TOKEN")
            body = create_call_log[0]["body"]
            self.assertEqual(body["intent"], "CAPTURE")
            self.assertEqual(body["purchase_units"][0]["amount"]["value"], "5.00")
            self.assertEqual(body["application_context"]["brand_name"], "CVCC (test)")

            self.assertEqual(len(capture_call_log), 1, f"capture calls: {capture_call_log!r}")
            self.assertEqual(capture_call_log[0]["order_id"], "FAKE_ORDER_001")
            self.assertEqual(capture_call_log[0]["base_url"], "https://api-m.sandbox.paypal.com")

            # The orders NDJSON log should contain both create + capture
            # events for FAKE_ORDER_001.
            orders_log = tmp / "private" / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"
            self.assertTrue(orders_log.exists(), f"missing orders log at {orders_log}")
            entries = [
                json.loads(line)
                for line in orders_log.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            events = [e.get("event") for e in entries]
            self.assertIn("create_order", events)
            self.assertIn("capture_order", events)
            for entry in entries:
                self.assertEqual(entry.get("order_id"), "FAKE_ORDER_001")
        finally:
            server.shutdown()
            thread.join(timeout=3)

    def test_missing_amount_returns_400_without_calling_paypal(self) -> None:
        from playwright.sync_api import sync_playwright

        unexpected_calls: list[str] = []

        def fake_called(*args, **kwargs):
            unexpected_calls.append("called")
            raise AssertionError("PayPal should not be hit when amount is missing")

        server, thread, base, _tmp = self._boot_portal()
        try:
            with patch.dict(
                "os.environ",
                {"PAYPAL_CLIENT_ID": _FAKE_CLIENT_ID, "PAYPAL_CLIENT_SECRET": _FAKE_CLIENT_SECRET},
            ), patch(
                "MyCiteV2.instances._shared.portal_host.app._get_paypal_access_token",
                side_effect=fake_called,
            ):
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    ctx = browser.new_context()
                    resp = ctx.request.post(
                        f"{base}/__fnd/paypal/create-order",
                        data=json.dumps({"amount": ""}),
                        headers={"Content-Type": "application/json"},
                    )
                    self.assertEqual(resp.status, 400)
                    body = resp.json()
                    self.assertFalse(body.get("ok"))
                    self.assertEqual(body.get("error"), "missing_amount")
                    browser.close()

            self.assertEqual(unexpected_calls, [], "early-return should short-circuit before PayPal")
        finally:
            server.shutdown()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
