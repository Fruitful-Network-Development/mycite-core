"""Phase 15c — Shared webdesign extension library postconditions.

The shared library lives at ``/srv/webapps/clients/_shared/site-core/
js/`` and gets distributed to each webdesign by
``sync_site_core.py``. These tests pin the layout + the canonical
contract (endpoint paths, public function names, data attributes)
so a future commit can't quietly drift any of the 3 sites away from
the uniform implementation.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WEBAPPS_ROOT = Path("/srv/webapps")
SITE_CORE = WEBAPPS_ROOT / "clients" / "_shared" / "site-core"
JS_DIR = SITE_CORE / "js"
EXT_DIR = JS_DIR / "extensions"


class SharedLibraryLayoutTests(unittest.TestCase):
    """Files exist at the canonical paths the sync script expects."""

    def test_form_utils_present(self) -> None:
        self.assertTrue((JS_DIR / "form-utils.js").is_file())

    def test_newsletter_extension_present(self) -> None:
        self.assertTrue((EXT_DIR / "newsletter.js").is_file())

    def test_donate_extension_present(self) -> None:
        self.assertTrue((EXT_DIR / "donate.js").is_file())

    def test_connect_extension_present(self) -> None:
        self.assertTrue((EXT_DIR / "connect.js").is_file())

    def test_analytics_extension_present(self) -> None:
        # Phase 18b: site-wide raw-event capture.
        self.assertTrue((EXT_DIR / "analytics.js").is_file())

    def test_extensions_doc_present(self) -> None:
        self.assertTrue((SITE_CORE / "docs" / "extensions.md").is_file())


class SharedLibraryContractTests(unittest.TestCase):
    """Pin the public surface + canonical endpoints by JS-text scan."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.utils = (JS_DIR / "form-utils.js").read_text(encoding="utf-8")
        cls.newsletter = (EXT_DIR / "newsletter.js").read_text(encoding="utf-8")
        cls.donate = (EXT_DIR / "donate.js").read_text(encoding="utf-8")
        cls.connect = (EXT_DIR / "connect.js").read_text(encoding="utf-8")
        cls.analytics = (EXT_DIR / "analytics.js").read_text(encoding="utf-8")

    def test_form_utils_exposes_canonical_names(self) -> None:
        for name in ("validateEmail", "normalizeText", "showBanner", "postJSON"):
            self.assertIn(name, self.utils, f"{name} missing from form-utils.js")
        self.assertIn("window.MyciteFormUtils", self.utils)

    def test_newsletter_targets_canonical_endpoint(self) -> None:
        self.assertIn("/__fnd/newsletter/subscribe", self.newsletter)
        self.assertIn("MyciteExtensions.mountNewsletterForm", self.newsletter)
        self.assertIn("data-mycite-newsletter", self.newsletter)

    def test_newsletter_reads_phone_and_zip(self) -> None:
        # Phase 16a: the public form posts phone + zip alongside the
        # split-name fields. Pin the JS reads them so a future refactor
        # can't silently drop them.
        self.assertIn('readField(form, "phone")', self.newsletter)
        self.assertIn('readField(form, "zip")', self.newsletter)

    def test_donate_targets_canonical_endpoints(self) -> None:
        self.assertIn("/__fnd/paypal/create-order", self.donate)
        self.assertIn("/__fnd/paypal/capture-order", self.donate)
        self.assertIn("MyciteExtensions.mountDonateForm", self.donate)
        self.assertIn("data-mycite-donate", self.donate)

    def test_connect_targets_canonical_endpoint(self) -> None:
        self.assertIn("/__fnd/connect/submit", self.connect)
        self.assertIn("MyciteExtensions.mountConnectForm", self.connect)
        self.assertIn("data-mycite-connect", self.connect)

    def test_analytics_targets_canonical_endpoint(self) -> None:
        # Phase 18b: every captured event POSTs here. Pin so a
        # rename can't silently break ingestion.
        self.assertIn("/__fnd/analytics/event", self.analytics)
        # Pin the auto-bind public name + the session key so future
        # refactors don't drift.
        self.assertIn("MyciteAnalytics", self.analytics)
        self.assertIn("fnd_analytics_session", self.analytics)
        # Required event types the JS produces.
        for et in ("page_view", "heartbeat", "outbound_click", "form_submit"):
            self.assertIn(et, self.analytics, f"event_type {et} not emitted")

    def test_connect_reads_full_field_set(self) -> None:
        # Phase 17d: pin the canonical Connect-form field names so a
        # rename can't silently drop one.
        for field in (
            "email",
            "message",
            "subject",
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "zip",
        ):
            self.assertIn(
                f'readField(form, "{field}")',
                self.connect,
                f"{field} not read in connect.js",
            )


class SiteSyncTargetsTests(unittest.TestCase):
    """Each of the 3 sites must carry the synced JS bundle alongside
    the synced CSS. Pinned to catch a partial sync (e.g. someone runs
    sync for one site and forgets the other two)."""

    def _frontend_for(self, host: str, case: str) -> Path:
        return WEBAPPS_ROOT / "clients" / host / "frontend" / case / "mycite-extensions"

    def test_tff_has_synced_bundle(self) -> None:
        d = self._frontend_for("trappfamilyfarm.com", "js")
        for leaf in (
            "form-utils.js",
            "newsletter.js",
            "donate.js",
            "connect.js",
            "analytics.js",
        ):
            self.assertTrue((d / leaf).is_file(), f"{d / leaf} missing")

    def test_cvcc_has_synced_bundle(self) -> None:
        d = self._frontend_for("cuyahogavalleycountrysideconservancy.org", "js")
        for leaf in (
            "form-utils.js",
            "newsletter.js",
            "donate.js",
            "connect.js",
            "analytics.js",
        ):
            self.assertTrue((d / leaf).is_file(), f"{d / leaf} missing")

    def test_fnd_has_synced_bundle(self) -> None:
        d = self._frontend_for("fruitfulnetworkdevelopment.com", "js")
        for leaf in (
            "form-utils.js",
            "newsletter.js",
            "donate.js",
            "connect.js",
            "analytics.js",
        ):
            self.assertTrue((d / leaf).is_file(), f"{d / leaf} missing")


class WebdesignFormWiringTests(unittest.TestCase):
    """The migrated forms must carry the right data attributes so the
    auto-mount picks them up. Catches accidental regressions in the
    HTML that would silently disable the shared library."""

    def test_tff_newsletter_uses_data_attribute(self) -> None:
        html = (
            WEBAPPS_ROOT
            / "clients"
            / "trappfamilyfarm.com"
            / "frontend"
            / "newsletter.html"
        ).read_text(encoding="utf-8")
        self.assertIn("data-mycite-newsletter", html)
        self.assertIn('data-domain="trappfamilyfarm.com"', html)
        # Split-name fields must be present so subscribers can supply
        # first/last (the schema Phase 15b expanded).
        self.assertIn('name="first_name"', html)
        self.assertIn('name="last_name"', html)
        # Phase 16b: phone + zip inputs land on the public form.
        self.assertIn('name="phone"', html)
        self.assertIn('name="zip"', html)
        # Shared lib must be loaded.
        self.assertIn("mycite-extensions/form-utils.js", html)
        self.assertIn("mycite-extensions/newsletter.js", html)

    def test_analytics_script_uses_absolute_path(self) -> None:
        # Phase 18b: relative ``__fnd/analytics.js`` resolves to
        # /<page-dir>/__fnd/analytics.js for any non-root page →
        # 404. Every HTML file that loads the analytics script must
        # use the absolute path ``/__fnd/analytics.js``.
        for host in (
            "trappfamilyfarm.com",
            "cuyahogavalleycountrysideconservancy.org",
            "fruitfulnetworkdevelopment.com",
        ):
            site_root = WEBAPPS_ROOT / "clients" / host / "frontend"
            for path in site_root.rglob("*.html"):
                content = path.read_text(encoding="utf-8")
                if "analytics.js" not in content:
                    continue
                # If the file references analytics.js at all, every
                # reference must be via the absolute path or the
                # site-relative mycite-extensions copy.
                self.assertNotIn(
                    'src="__fnd/analytics.js"',
                    content,
                    f"{path} uses relative analytics path",
                )
                self.assertNotIn(
                    'src="./__fnd/analytics.js"',
                    content,
                    f"{path} uses relative analytics path",
                )

    def test_no_site_posts_to_legacy_newsletter_endpoint(self) -> None:
        # Phase 16b: the legacy ``/newsletter/subscribe`` (without
        # __fnd prefix) is gone from every site's frontend + source
        # manifests. The canonical endpoint is /__fnd/newsletter/
        # subscribe, which all 3 sites share via the FND portal.
        for host in (
            "trappfamilyfarm.com",
            "cuyahogavalleycountrysideconservancy.org",
            "fruitfulnetworkdevelopment.com",
        ):
            site_root = WEBAPPS_ROOT / "clients" / host / "frontend"
            for path in site_root.rglob("*.html"):
                content = path.read_text(encoding="utf-8")
                self.assertNotIn(
                    "'/newsletter/subscribe'",
                    content,
                    f"{path} still posts to the legacy endpoint",
                )
                self.assertNotIn(
                    '"/newsletter/subscribe"',
                    content,
                    f"{path} still posts to the legacy endpoint",
                )

    def test_cvcc_donate_uses_data_attribute(self) -> None:
        html = (
            WEBAPPS_ROOT
            / "clients"
            / "cuyahogavalleycountrysideconservancy.org"
            / "frontend"
            / "donate.html"
        ).read_text(encoding="utf-8")
        self.assertIn("data-mycite-donate", html)
        self.assertIn(
            'data-domain="cuyahogavalleycountrysideconservancy.org"', html
        )
        self.assertIn("mycite-extensions/form-utils.js", html)
        self.assertIn("mycite-extensions/donate.js", html)

    def test_fnd_contact_uses_canonical_endpoint(self) -> None:
        html = (
            WEBAPPS_ROOT
            / "clients"
            / "fruitfulnetworkdevelopment.com"
            / "frontend"
            / "contact.html"
        ).read_text(encoding="utf-8")
        # Phase 17d: the FND contact page is now the canonical Connect
        # form (data-mycite-connect). The newsletter-subscribe POST
        # still fires when the "Also subscribe" checkbox is checked,
        # but it uses the canonical /__fnd/newsletter/subscribe path
        # and is wired as a side-effect of the Connect submission.
        self.assertIn("data-mycite-connect", html)
        self.assertIn('data-domain="fruitfulnetworkdevelopment.com"', html)
        self.assertIn("mycite-extensions/connect.js", html)
        self.assertIn("/__fnd/newsletter/subscribe", html)
        self.assertNotIn("'/newsletter/subscribe'", html)
        # Split-name fields from Phase 15b carried through.
        self.assertIn('name="first_name"', html)
        self.assertIn('name="last_name"', html)
        # Required Connect-form fields.
        self.assertIn('name="message"', html)
        self.assertIn('name="subject"', html)


if __name__ == "__main__":
    unittest.main()
