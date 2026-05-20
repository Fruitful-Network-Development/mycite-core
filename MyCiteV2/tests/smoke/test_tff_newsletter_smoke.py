"""TFF newsletter preservation smoke (Phase 13d.1).

Boots a tempdir-backed FND portal on a free local port, registers a
test-only route that serves a minimal ``newsletter.html`` fixture, then
drives Chromium at it to:

  1. POST the subscribe form against the live ``/__fnd/newsletter/subscribe``
     handler.
  2. Verify the route accepts the request (domain is in
     ``_newsletter_known_domains(host_config.private_dir)``).
  3. Verify the canonical mutation runtime is invoked with the right
     ``target_authority + operation + domain + email`` (mocked so the
     smoke doesn't require a fully-bootstrapped MOS authority db).

This is the closest a CI-runnable smoke can get to the real production
flow at https://trappfamilyfarm.com/newsletter without driving
production traffic. No production HTTP is generated.

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


# Use 127.0.0.1 as the "domain": Chromium blocks overriding the Host header
# via extra_http_headers (security restriction), so the smoke takes the Host
# header the browser actually sends. _normalize_domain strips the port, so
# "127.0.0.1:55649" → "127.0.0.1".
_TFF_DOMAIN = "127.0.0.1"

_NEWSLETTER_HTML = """\
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>TFF Newsletter Smoke</title></head>
<body>
  <h1>Newsletter</h1>
  <form id="subscribe" method="POST" action="/__fnd/newsletter/subscribe">
    <input type="email" name="email" required>
    <input type="text" name="name">
    <input type="text" name="zip">
    <button type="submit">Subscribe</button>
  </form>
  <pre id="result"></pre>
  <script>
    document.getElementById("subscribe").addEventListener("submit", function (e) {
      e.preventDefault();
      var form = e.target;
      var body = new FormData(form);
      fetch(form.action, { method: "POST", body: body })
        .then(function (r) { return r.json().then(function (j) { return {status: r.status, body: j}; }); })
        .then(function (out) {
          document.getElementById("result").textContent = JSON.stringify(out);
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


def _seed_tff_newsletter_admin_profile(private_dir: Path) -> None:
    admin_dir = private_dir / "utilities" / "tools" / "newsletter-admin"
    admin_dir.mkdir(parents=True, exist_ok=True)
    (admin_dir / f"newsletter-admin.{_TFF_DOMAIN}.json").write_text(
        json.dumps({"domain": _TFF_DOMAIN, "label": "TFF (test)"}),
        encoding="utf-8",
    )


@unittest.skipUnless(
    PLAYWRIGHT_AVAILABLE and FLASK_AVAILABLE and WERKZEUG_AVAILABLE,
    "Browser smoke requires playwright + flask + werkzeug in the venv "
    "(playwright install chromium also required).",
)
class TffNewsletterSmokeTests(unittest.TestCase):
    def _boot_portal(self) -> tuple:
        tmp = Path(tempfile.mkdtemp(prefix="tff_newsletter_smoke_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        _seed_tff_newsletter_admin_profile(tmp / "private")
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain=_TFF_DOMAIN,
            webapps_root=tmp / "webapps",
        )
        app = create_app(config)

        # Test-only route serving the newsletter HTML fixture. Same-origin
        # with the portal so the form's relative action POSTs back to
        # /__fnd/newsletter/subscribe.
        from flask import Response

        @app.route("/__test/newsletter.html")
        def serve_newsletter_fixture():  # pragma: no cover - trivial
            return Response(_NEWSLETTER_HTML, mimetype="text/html")

        port = _free_port()
        from werkzeug.serving import make_server

        server = make_server("127.0.0.1", port, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.4)
        return server, thread, f"http://127.0.0.1:{port}"

    def test_newsletter_subscribe_form_round_trips_to_mutation_runtime(self) -> None:
        from playwright.sync_api import sync_playwright

        # Mock the canonical mutation runtime so the smoke doesn't need a
        # fully-bootstrapped MOS authority db. The smoke verifies the route
        # handler reaches the mutation layer with the right arguments — the
        # storage layer is exercised by unit tests on the mutation runtime
        # directly.
        captured_calls: list[tuple] = []

        def fake_mutation(action: str, payload: dict, **kwargs):
            captured_calls.append((action, dict(payload), dict(kwargs)))
            return {"ok": True, "applied_row": payload.get("email", "")}

        server, thread, base = self._boot_portal()
        try:
            with patch(
                "MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime.run_datum_workbench_mutation_action",
                side_effect=fake_mutation,
            ):
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    ctx = browser.new_context()
                    page = ctx.new_page()
                    page.goto(f"{base}/__test/newsletter.html", wait_until="networkidle", timeout=15000)

                    # Fill + submit form, then wait for the resulting
                    # /__fnd/newsletter/subscribe POST + the page's
                    # #result element to populate.
                    page.fill('input[name="email"]', "subscriber@example.test")
                    page.fill('input[name="name"]', "Test Subscriber")
                    with page.expect_response(
                        lambda r: "/__fnd/newsletter/subscribe" in r.url
                        and r.request.method == "POST",
                        timeout=10000,
                    ) as resp_info:
                        page.click("button[type=submit]")
                    resp = resp_info.value
                    self.assertEqual(resp.status, 200)
                    body = resp.json()
                    self.assertTrue(body.get("ok"), f"subscribe returned {body!r}")

                    browser.close()

            # Mutation should have been called exactly once with the
            # canonical (target_authority, operation, domain, email)
            # tuple.
            self.assertEqual(len(captured_calls), 1, f"calls={captured_calls!r}")
            action, payload, _kwargs = captured_calls[0]
            self.assertEqual(action, "apply")
            self.assertEqual(payload["target_authority"], "newsletter_contact_log")
            self.assertEqual(payload["operation"], "upsert_subscriber")
            self.assertEqual(payload["domain"], _TFF_DOMAIN)
            self.assertEqual(payload["email"], "subscriber@example.test")
            self.assertEqual(payload["name"], "Test Subscriber")
        finally:
            server.shutdown()
            thread.join(timeout=3)

    def test_invalid_email_returns_400(self) -> None:
        from playwright.sync_api import sync_playwright

        server, thread, base = self._boot_portal()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context()
                resp = ctx.request.post(
                    f"{base}/__fnd/newsletter/subscribe",
                    form={"email": "not-an-email"},
                )
                self.assertEqual(resp.status, 400)
                body = resp.json()
                self.assertFalse(body.get("ok"))
                self.assertEqual(body.get("error"), "invalid_email")
                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
