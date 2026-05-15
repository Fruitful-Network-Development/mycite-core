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

    def test_extensions_doc_present(self) -> None:
        self.assertTrue((SITE_CORE / "docs" / "extensions.md").is_file())


class SharedLibraryContractTests(unittest.TestCase):
    """Pin the public surface + canonical endpoints by JS-text scan."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.utils = (JS_DIR / "form-utils.js").read_text(encoding="utf-8")
        cls.newsletter = (EXT_DIR / "newsletter.js").read_text(encoding="utf-8")
        cls.donate = (EXT_DIR / "donate.js").read_text(encoding="utf-8")

    def test_form_utils_exposes_canonical_names(self) -> None:
        for name in ("validateEmail", "normalizeText", "showBanner", "postJSON"):
            self.assertIn(name, self.utils, f"{name} missing from form-utils.js")
        self.assertIn("window.MyciteFormUtils", self.utils)

    def test_newsletter_targets_canonical_endpoint(self) -> None:
        self.assertIn("/__fnd/newsletter/subscribe", self.newsletter)
        self.assertIn("MyciteExtensions.mountNewsletterForm", self.newsletter)
        self.assertIn("data-mycite-newsletter", self.newsletter)

    def test_donate_targets_canonical_endpoints(self) -> None:
        self.assertIn("/__fnd/paypal/create-order", self.donate)
        self.assertIn("/__fnd/paypal/capture-order", self.donate)
        self.assertIn("MyciteExtensions.mountDonateForm", self.donate)
        self.assertIn("data-mycite-donate", self.donate)


class SiteSyncTargetsTests(unittest.TestCase):
    """Each of the 3 sites must carry the synced JS bundle alongside
    the synced CSS. Pinned to catch a partial sync (e.g. someone runs
    sync for one site and forgets the other two)."""

    def _frontend_for(self, host: str, case: str) -> Path:
        return WEBAPPS_ROOT / "clients" / host / "frontend" / case / "mycite-extensions"

    def test_tff_has_synced_bundle(self) -> None:
        d = self._frontend_for("trappfamilyfarm.com", "js")
        for leaf in ("form-utils.js", "newsletter.js", "donate.js"):
            self.assertTrue((d / leaf).is_file(), f"{d / leaf} missing")

    def test_cvcc_has_synced_bundle(self) -> None:
        d = self._frontend_for("cuyahogavalleycountrysideconservancy.org", "JS")
        for leaf in ("form-utils.js", "newsletter.js", "donate.js"):
            self.assertTrue((d / leaf).is_file(), f"{d / leaf} missing")

    def test_fnd_has_synced_bundle(self) -> None:
        d = self._frontend_for("fruitfulnetworkdevelopment.com", "js")
        for leaf in ("form-utils.js", "newsletter.js", "donate.js"):
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
        # Shared lib must be loaded.
        self.assertIn("mycite-extensions/form-utils.js", html)
        self.assertIn("mycite-extensions/newsletter.js", html)

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
        # Phase 15c normalized FND off the legacy /newsletter/subscribe
        # path; Phase 15 deferred a full migration of the contact-form
        # checkbox to the data-mycite-newsletter auto-mount.
        self.assertIn("/__fnd/newsletter/subscribe", html)
        self.assertNotIn("'/newsletter/subscribe'", html)


if __name__ == "__main__":
    unittest.main()
