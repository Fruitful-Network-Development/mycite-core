"""Phase 12h headless browser smoke.

End-to-end check that:

  1. The utilities tool-exposure surface payload carries a
     ``grantee_selector`` listing every grantee, with ``active`` and
     ``select_action`` per entry.
  2. Switching grantees via ``surface_query.selected_grantee_msn``
     rewires ``ext_paypal.payload.domain`` (and the other extensions).
  3. The JS workbench renderer mounts a ``.v2-granteeSelector`` card
     with one ``.v2-granteeSelector__option.is-active`` and clickable
     inactive options that POST to ``/portal/api/v2/shell`` with the
     right msn_id.

This is the only test in the suite that loads the actual JS in a real
browser — the rest are pure-Python contract tests. It catches the class
of bug that landed in Phase 12c (orphan function body) and the 12g
fallback regression (selector hidden behind a stale region.sections
check) that Python tests cannot see.

Runtime
=======
Requires playwright and chromium-headless-shell in the venv::

    /srv/venvs/fnd_portal/bin/pip install playwright
    /srv/venvs/fnd_portal/bin/playwright install chromium

When either is absent the test is skipped — the suite stays green on
hosts that haven't run the install (most local dev boxes). CI is
expected to install both before running this directory.

It boots a Flask app on a free localhost port with a tempdir-backed
config so no production traffic is generated. Tempdir cleans up at
exit.
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
                "users": [],
            }
        ),
        encoding="utf-8",
    )


@unittest.skipUnless(
    PLAYWRIGHT_AVAILABLE and FLASK_AVAILABLE and WERKZEUG_AVAILABLE,
    "Browser smoke requires playwright + flask + werkzeug in the venv "
    "(playwright install chromium also required).",
)
class Phase12hBrowserSmokeTests(unittest.TestCase):
    def _boot_portal(self):
        tmp = Path(tempfile.mkdtemp(prefix="phase12h_smoke_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        grantee_dir = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        _seed_grantee(grantee_dir, "alpha", "Alpha Grantee", ["alpha.example.org"])
        _seed_grantee(grantee_dir, "beta", "Beta Grantee", ["beta.example.org"])
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.org",
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

    def test_grantee_selector_renders_dispatches_and_pivots_extension_payloads(self) -> None:
        from playwright.sync_api import sync_playwright

        server, thread, base = self._boot_portal()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context()
                page = ctx.new_page()

                # API contract — grantee_selector on the surface payload.
                # Phase 14b: the grantee selector now lives on
                # ``utilities.extensions`` (the legacy tool_exposure surface
                # is retained but 302-redirects from its HTTP route).
                # Phase 15a: ext_paypal lives behind a subtab — request it
                # explicitly via selected_extension_tool_id so the API
                # returns the paypal card.
                # Refactor: the surface now DEFAULTS to the global ("Overall")
                # view, so select a grantee explicitly to exercise the
                # per-grantee extension payload pivot.
                api_resp = page.request.post(
                    f"{base}/portal/api/v2/shell",
                    data=json.dumps(
                        {
                            "schema": "mycite.v2.portal.shell.request.v1",
                            "requested_surface_id": "utilities.extensions",
                            "surface_query": {
                                "selected_grantee_msn": "alpha",
                                "selected_extension_tool_id": "ext_paypal",
                            },
                        }
                    ),
                    headers={"content-type": "application/json"},
                )
                self.assertEqual(api_resp.status, 200)
                payload = api_resp.json()
                surface = payload.get("surface_payload") or {}
                selector = surface.get("grantee_selector")
                self.assertIsNotNone(selector, "grantee_selector missing from surface_payload")
                # The list leads with a synthetic "All — Overall" entry; the
                # real grantees follow.
                self.assertEqual(
                    sorted(
                        g["msn_id"]
                        for g in (selector.get("grantees") or [])
                        if not g.get("is_overall")
                    ),
                    ["alpha", "beta"],
                )
                self.assertEqual(
                    len([g for g in selector["grantees"] if g.get("active")]),
                    1,
                    "exactly one entry should be active",
                )

                # Switching grantees via surface_query pivots extension domain.
                # Phase 15a: pin the paypal tab too — without it the active tab
                # defaults to ext_aws_email and the paypal card isn't in the
                # response.
                api_resp2 = page.request.post(
                    f"{base}/portal/api/v2/shell",
                    data=json.dumps(
                        {
                            "schema": "mycite.v2.portal.shell.request.v1",
                            "requested_surface_id": "utilities.extensions",
                            "surface_query": {
                                "selected_grantee_msn": "beta",
                                "selected_extension_tool_id": "ext_paypal",
                            },
                        }
                    ),
                    headers={"content-type": "application/json"},
                )
                surface2 = (api_resp2.json() or {}).get("surface_payload") or {}
                self.assertEqual(
                    surface2["grantee_selector"]["selected_grantee_msn"],
                    "beta",
                )

                def _ext_domain(p, tool_id):
                    for ext in p.get("extensions") or []:
                        if ext.get("tool_id") == tool_id:
                            return (ext.get("payload") or {}).get("domain")
                    return None

                self.assertEqual(_ext_domain(surface, "ext_paypal"), "alpha.example.org")
                self.assertEqual(_ext_domain(surface2, "ext_paypal"), "beta.example.org")

                # DOM contract — selector card renders, click dispatches.
                # Phase 14b: navigate to the new extensions surface (the
                # legacy /tool-exposure URL 302-redirects to this anyway).
                page.goto(
                    f"{base}/portal/utilities/extensions",
                    wait_until="networkidle",
                    timeout=15000,
                )
                try:
                    page.wait_for_response(
                        lambda r: "/portal/api/v2/shell" in r.url
                        and r.request.method == "POST",
                        timeout=10000,
                    )
                except Exception:
                    pass  # may have completed before the listener registered

                page.wait_for_selector(".v2-granteeSelector", timeout=10000)
                option_count = page.eval_on_selector_all(
                    ".v2-granteeSelector__option", "els => els.length"
                )
                active_count = page.eval_on_selector_all(
                    ".v2-granteeSelector__option.is-active", "els => els.length"
                )
                # 3 options: the synthetic "All — Overall" entry + the 2
                # grantees. On a default (no-query) load the surface is in the
                # global view, so the Overall entry is the single active one.
                self.assertEqual(option_count, 3)
                self.assertEqual(active_count, 1)

                with page.expect_response(
                    lambda r: "/portal/api/v2/shell" in r.url
                    and r.request.method == "POST",
                    timeout=5000,
                ) as resp_info:
                    page.click(".v2-granteeSelector__option:not(.is-active)")
                clicked_resp = resp_info.value
                req_body = json.loads(clicked_resp.request.post_data or "{}")
                clicked_msn = (req_body.get("surface_query") or {}).get("selected_grantee_msn")
                self.assertIn(clicked_msn, {"alpha", "beta"})

                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
