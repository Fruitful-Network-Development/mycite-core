"""Phase 14a DOM visibility smoke — extensions surface payloads reach the user.

Boots a tempdir-backed portal with a seeded grantee, navigates Chromium
to ``/portal/utilities/tool-exposure`` (the surface 14b will rename to
``/portal/utilities/extensions``), and asserts the 5 extension cards
render in the DOM with the right ``data-tool-id`` attributes.

Before Phase 14a, the surface payload's ``extensions`` array was built
server-side but the JS renderer dropped it silently — operators saw
the grantee selector at top and a tool-posture table, with nothing
below. This smoke is the regression pin so the gap can't reopen.
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

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None
FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None
WERKZEUG_AVAILABLE = importlib.util.find_spec("werkzeug") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app
    from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA


_EXPECTED_TOOL_IDS = {
    "ext_aws_email",
    "ext_analytics",
    "ext_newsletter",
    "ext_paypal",
    "ext_grantee_profile",
}


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _seed_grantee(grantee_dir: Path, msn_id: str, label: str, domains: list) -> None:
    grantee_dir.mkdir(parents=True, exist_ok=True)
    (grantee_dir / f"grantee.fnd-msn.{msn_id}.json").write_text(
        json.dumps(
            {
                "schema": GRANTEE_PROFILE_SCHEMA,
                "msn_id": msn_id,
                "label": label,
                "short_name": msn_id,
                "domains": domains,
                "users": ["operator@example.test"],
                "paypal": {
                    "webhook_url": "https://example.test/__fnd/paypal/webhook",
                    "environment": "sandbox",
                },
                "aws_ses": {"region": "us-east-1", "identity": "noreply@example.test"},
                "newsletter": {"selected_sender_address": "hello@example.test"},
            }
        ),
        encoding="utf-8",
    )


@unittest.skipUnless(
    PLAYWRIGHT_AVAILABLE and FLASK_AVAILABLE and WERKZEUG_AVAILABLE,
    "Browser smoke requires playwright + flask + werkzeug in the venv "
    "(playwright install chromium also required).",
)
class UtilitiesExtensionsVisibleSmokeTests(unittest.TestCase):
    def _boot_portal(self):
        tmp = Path(tempfile.mkdtemp(prefix="phase14a_visible_smoke_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        grantee_dir = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        _seed_grantee(grantee_dir, "alpha", "Alpha Grantee", ["alpha.example.test"])
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        app = create_app(config)
        port = _free_port()
        from werkzeug.serving import make_server

        server = make_server("127.0.0.1", port, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.4)
        return server, thread, f"http://127.0.0.1:{port}"

    def test_extension_cards_render_with_tool_ids(self) -> None:
        from playwright.sync_api import sync_playwright

        server, thread, base = self._boot_portal()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context()
                page = ctx.new_page()
                page.goto(
                    f"{base}/portal/utilities/tool-exposure",
                    wait_until="networkidle",
                    timeout=15000,
                )
                # Shell hydration may post after networkidle; wait for the
                # extension cards explicitly.
                page.wait_for_selector(".v2-extensionCard", timeout=10000)
                tool_ids = page.eval_on_selector_all(
                    ".v2-extensionCard",
                    "els => els.map(e => e.getAttribute('data-tool-id'))",
                )
                self.assertEqual(
                    set(tool_ids),
                    _EXPECTED_TOOL_IDS,
                    f"DOM extension cards: {tool_ids!r}",
                )
                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=3)

    def test_grantee_profile_form_renders_via_extension_card(self) -> None:
        from playwright.sync_api import sync_playwright

        server, thread, base = self._boot_portal()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context()
                page = ctx.new_page()
                page.goto(
                    f"{base}/portal/utilities/tool-exposure",
                    wait_until="networkidle",
                    timeout=15000,
                )
                page.wait_for_selector(
                    '.v2-extensionCard[data-tool-id="ext_grantee_profile"] form[data-form-submit-route]',
                    timeout=10000,
                )
                submit_route = page.eval_on_selector(
                    '.v2-extensionCard[data-tool-id="ext_grantee_profile"] form[data-form-submit-route]',
                    "el => el.getAttribute('data-form-submit-route')",
                )
                self.assertEqual(submit_route, "/__fnd/grantee/save")
                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
