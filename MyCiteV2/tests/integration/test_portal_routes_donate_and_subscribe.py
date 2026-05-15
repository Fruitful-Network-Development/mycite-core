"""
Phase 0 preservation pins for the portal simplification (TASK-PORTAL-SIMPLIFICATION-2026-05-14).

These tests guard the two load-bearing production paths named in
portal_tool_surface_contract.md:

    CVCC donations:  donate.html -> /__fnd/paypal/{create,capture}-order
    TFF newsletter:  newsletter.html -> /__fnd/newsletter/{subscribe,unsubscribe}

They must keep passing across every later phase. If a phase removes one of these
routes, that is a contract violation and the change should be reverted.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app


TFF_NEWSLETTER_HTML = Path(
    "/srv/webapps/clients/trappfamilyfarm.com/frontend/newsletter.html"
)


class _SubscribeFormParser(HTMLParser):
    """Locate the TFF subscribe form and its email input."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.subscribe_form_found = False
        self._in_subscribe_form = False
        self.email_input_required = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k: (v or "") for k, v in attrs}
        if tag == "form" and attr_map.get("action") == "/__fnd/newsletter/subscribe":
            method = attr_map.get("method", "").lower()
            if method == "post":
                self.subscribe_form_found = True
                self._in_subscribe_form = True
        elif self._in_subscribe_form and tag == "input":
            if (
                attr_map.get("type") == "email"
                and attr_map.get("name") == "email"
                and "required" in attr_map
            ):
                self.email_input_required = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._in_subscribe_form:
            self._in_subscribe_form = False


@unittest.skipUnless(TFF_NEWSLETTER_HTML.exists(), "TFF newsletter.html not present in this environment")
class TestTffNewsletterForm(unittest.TestCase):
    def test_tff_newsletter_form_present_and_posts_email(self) -> None:
        html = TFF_NEWSLETTER_HTML.read_text(encoding="utf-8")
        parser = _SubscribeFormParser()
        parser.feed(html)
        self.assertTrue(
            parser.subscribe_form_found,
            "TFF newsletter.html must contain <form action=\"/__fnd/newsletter/subscribe\" method=\"post\"> "
            "(preservation invariant from portal_tool_surface_contract.md)",
        )
        self.assertTrue(
            parser.email_input_required,
            "TFF subscribe form must contain <input type=\"email\" name=\"email\" required>",
        )


def _build_minimal_portal_app():
    """Instantiate the portal Flask app against a tempdir for url_map inspection."""
    tmp_root = tempfile.mkdtemp(prefix="portal_routes_pin_")
    base = Path(tmp_root)
    (base / "public").mkdir(parents=True, exist_ok=True)
    (base / "private").mkdir(parents=True, exist_ok=True)
    (base / "data").mkdir(parents=True, exist_ok=True)
    (base / "webapps").mkdir(parents=True, exist_ok=True)
    config = V2PortalHostConfig(
        portal_instance_id="fnd",
        public_dir=base / "public",
        private_dir=base / "private",
        data_dir=base / "data",
        portal_domain="fruitfulnetworkdevelopment.com",
        webapps_root=base / "webapps",
    )
    return create_app(config)


def _route_methods_for(app, rule: str) -> set[str]:
    for r in app.url_map.iter_rules():
        if r.rule == rule:
            return set(r.methods or set())
    return set()


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class TestPreservationRoutesRegistered(unittest.TestCase):
    """url_map regression pins. If any route disappears, a later phase has broken the contract."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _build_minimal_portal_app()

    def test_paypal_create_order_route_registered(self) -> None:
        self.assertIn("POST", _route_methods_for(self.app, "/__fnd/paypal/create-order"))

    def test_paypal_capture_order_route_registered(self) -> None:
        self.assertIn("POST", _route_methods_for(self.app, "/__fnd/paypal/capture-order"))

    def test_newsletter_subscribe_route_registered(self) -> None:
        self.assertIn("POST", _route_methods_for(self.app, "/__fnd/newsletter/subscribe"))

    def test_newsletter_unsubscribe_route_registered(self) -> None:
        self.assertIn("POST", _route_methods_for(self.app, "/__fnd/newsletter/unsubscribe"))


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class TestNewsletterKnownDomainsResolution(unittest.TestCase):
    """The newsletter known-domains lookup must derive from the host config's
    private_dir (V2PortalHostConfig.private_dir / utilities/tools/newsletter-admin/),
    not from a hardcoded /srv/mycite-state path. Phase 13d-prep refactor — the
    smoke tests will rely on this so they can boot the portal against a tempdir.
    """

    def test_known_domains_reads_from_host_config_private_dir(self) -> None:
        from MyCiteV2.instances._shared.portal_host.app import _newsletter_known_domains

        with tempfile.TemporaryDirectory(prefix="newsletter_admin_") as tmp:
            private_dir = Path(tmp)
            admin_dir = private_dir / "utilities" / "tools" / "newsletter-admin"
            admin_dir.mkdir(parents=True, exist_ok=True)
            for slug in ("alpha.example.test", "beta.example.test"):
                (admin_dir / f"newsletter-admin.{slug}.json").write_text("{}\n", encoding="utf-8")

            self.assertEqual(
                _newsletter_known_domains(private_dir),
                ["alpha.example.test", "beta.example.test"],
            )

    def test_known_domains_returns_empty_when_admin_dir_missing(self) -> None:
        from MyCiteV2.instances._shared.portal_host.app import _newsletter_known_domains

        with tempfile.TemporaryDirectory(prefix="newsletter_admin_empty_") as tmp:
            # No utilities/tools/newsletter-admin/ subdirectory at all.
            self.assertEqual(_newsletter_known_domains(Path(tmp)), [])


if __name__ == "__main__":
    unittest.main()
