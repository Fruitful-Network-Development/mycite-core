"""Integration tests for ``GET /__fnd/donation/receipt-document`` +
capture-order ``receipt_document_url`` response shaping.

Covers:
  - receipt-document route returns 200 + PDF bytes + attachment disposition
    when configured.
  - receipt-document route returns 404 for unconfigured / missing /
    path-traversal cases.
  - capture-order response includes ``receipt_document_url`` when status is
    COMPLETED and the domain has a configured receipt artifact.
  - capture-order response omits ``receipt_document_url`` when no artifact
    is configured.
  - capture-order response omits ``receipt_document_url`` when capture
    status is not COMPLETED (e.g. DECLINED / PENDING).

Production receipts live under
``/srv/webapps/clients/_shared/site-core/document/`` which the route hard-pins
as the artifact parent. The tests inject fake paypal-csm domain configs
referencing files that either exist under that parent (the real CVCC PDF
suits the happy-path) or attempt to escape (which must be rejected).
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


_RECEIPT_PARENT = Path("/srv/webapps/clients/_shared/site-core/document")
_CVCC_PDF_NAME = (
    "2026-05-13.artifact-document.cuyahoga_valley_countryide_conservancy_inc."
    "blanket_sales_tax_exempt_certificate.pdf"
)


def _seed_domain_profile(
    private_dir: Path, *, domain: str, receipt_artifact_path: str | None
) -> None:
    tool_dir = private_dir / "utilities" / "tools" / "paypal-csm"
    tool_dir.mkdir(parents=True, exist_ok=True)
    profile: dict = {
        "schema": "portals.paypal.domain.config.v1",
        "domain": domain,
        "tenant_ref": "1",
        "environment": "sandbox",
        "brand_name": "Test",
        "checkout_context": {
            "return_url": f"https://{domain}/donate?paypal=return",
            "cancel_url": f"https://{domain}/donate?paypal=cancel",
            "currency_code": "USD",
            "intent": "CAPTURE",
        },
        "donation_defaults": {
            "item_name": "Donation",
            "item_description": "Tax-deductible contribution.",
            "custom_id_prefix": "donation",
        },
    }
    if receipt_artifact_path is not None:
        profile["donation_defaults"]["receipt_artifact_path"] = receipt_artifact_path
    slug = domain.replace(".", "_")
    (tool_dir / f"paypal-csm.{slug}.json").write_text(
        json.dumps(profile), encoding="utf-8"
    )


def _build_app(private_dir: Path):
    (private_dir.parent / "public").mkdir(parents=True, exist_ok=True)
    (private_dir.parent / "data").mkdir(parents=True, exist_ok=True)
    (private_dir.parent / "webapps").mkdir(parents=True, exist_ok=True)
    config = V2PortalHostConfig(
        portal_instance_id="fnd",
        public_dir=private_dir.parent / "public",
        private_dir=private_dir,
        data_dir=private_dir.parent / "data",
        portal_domain="fruitfulnetworkdevelopment.com",
        webapps_root=private_dir.parent / "webapps",
    )
    return create_app(config)


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
@unittest.skipUnless(
    (_RECEIPT_PARENT / _CVCC_PDF_NAME).exists(),
    "Shared CVCC receipt PDF not present in this environment",
)
class TestDonationReceiptRoute(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="receipt_route_")
        self.tmp_root = Path(self._tmp.name)
        self.private_dir = self.tmp_root / "private"
        self.private_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_pdf_when_configured(self) -> None:
        domain = "happy-path.example.test"
        _seed_domain_profile(
            self.private_dir, domain=domain, receipt_artifact_path=_CVCC_PDF_NAME
        )
        app = _build_app(self.private_dir)
        client = app.test_client()
        resp = client.get(
            f"/__fnd/donation/receipt-document?domain={domain}"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/pdf")
        # Flask's send_from_directory sets the attachment disposition.
        self.assertIn("attachment", resp.headers.get("Content-Disposition", "").lower())
        self.assertGreater(len(resp.data), 100_000)
        self.assertTrue(resp.data.startswith(b"%PDF"))

    def test_returns_404_when_domain_has_no_receipt_configured(self) -> None:
        domain = "no-receipt.example.test"
        _seed_domain_profile(self.private_dir, domain=domain, receipt_artifact_path=None)
        app = _build_app(self.private_dir)
        client = app.test_client()
        resp = client.get(f"/__fnd/donation/receipt-document?domain={domain}")
        self.assertEqual(resp.status_code, 404)

    def test_returns_404_when_no_domain_profile_exists(self) -> None:
        # No domain profile seeded at all.
        app = _build_app(self.private_dir)
        client = app.test_client()
        resp = client.get(
            "/__fnd/donation/receipt-document?domain=unknown.example.test"
        )
        self.assertEqual(resp.status_code, 404)

    def test_returns_404_for_path_traversal_dotdot(self) -> None:
        domain = "traverse.example.test"
        _seed_domain_profile(
            self.private_dir,
            domain=domain,
            receipt_artifact_path="../../../etc/passwd",
        )
        app = _build_app(self.private_dir)
        client = app.test_client()
        resp = client.get(f"/__fnd/donation/receipt-document?domain={domain}")
        self.assertEqual(resp.status_code, 404)

    def test_returns_404_for_absolute_path(self) -> None:
        domain = "absolute.example.test"
        _seed_domain_profile(
            self.private_dir,
            domain=domain,
            receipt_artifact_path="/etc/passwd",
        )
        app = _build_app(self.private_dir)
        client = app.test_client()
        resp = client.get(f"/__fnd/donation/receipt-document?domain={domain}")
        self.assertEqual(resp.status_code, 404)

    def test_returns_404_when_configured_file_missing(self) -> None:
        domain = "missing-file.example.test"
        _seed_domain_profile(
            self.private_dir,
            domain=domain,
            receipt_artifact_path="this-file-does-not-exist.pdf",
        )
        app = _build_app(self.private_dir)
        client = app.test_client()
        resp = client.get(f"/__fnd/donation/receipt-document?domain={domain}")
        self.assertEqual(resp.status_code, 404)


def _seed_tenant_config(private_dir: Path) -> None:
    tenants_dir = private_dir / "utilities" / "tools" / "paypal-csm" / "tenants"
    tenants_dir.mkdir(parents=True, exist_ok=True)
    (tenants_dir / "1.json").write_text(
        json.dumps({"credentials_ref": "1"}),
        encoding="utf-8",
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
@unittest.skipUnless(
    (_RECEIPT_PARENT / _CVCC_PDF_NAME).exists(),
    "Shared CVCC receipt PDF not present in this environment",
)
class TestCaptureOrderReceiptUrl(unittest.TestCase):
    """The capture-order response carries ``receipt_document_url`` only
    when the capture status is COMPLETED **and** the domain has a
    configured receipt artifact. Both halves are necessary — without
    them the donate.html injection branch is dead code.
    """

    DOMAIN = "localhost"  # Flask test_client reports request.host as localhost.

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="capture_receipt_")
        self.tmp_root = Path(self._tmp.name)
        self.private_dir = self.tmp_root / "private"
        self.private_dir.mkdir(parents=True, exist_ok=True)
        _seed_tenant_config(self.private_dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _patches(self, status: str = "COMPLETED"):
        from unittest.mock import patch

        def fake_token(*args, **kwargs) -> str:
            return "FAKE_TOKEN"

        capture_result = {
            "id": "ORDER_RECEIPT_TEST",
            "status": status,
            "purchase_units": [{
                "payments": {"captures": [{
                    "id": "CAP_RECEIPT_TEST",
                    "amount": {"value": "10.00", "currency_code": "USD"},
                }]},
            }],
        }

        def fake_capture(*, access_token, base_url, order_id):
            return capture_result

        return (
            patch.dict(
                "os.environ",
                {
                    "PAYPAL_CLIENT_ID": "FAKE_ID",
                    "PAYPAL_CLIENT_SECRET": "FAKE_SECRET",
                },
            ),
            patch(
                "MyCiteV2.instances._shared.portal_host.app._get_paypal_access_token",
                side_effect=fake_token,
            ),
            patch(
                "MyCiteV2.instances._shared.portal_host.app._capture_paypal_order",
                side_effect=fake_capture,
            ),
        )

    def test_capture_response_includes_receipt_url_when_completed(self) -> None:
        _seed_domain_profile(
            self.private_dir,
            domain=self.DOMAIN,
            receipt_artifact_path=_CVCC_PDF_NAME,
        )
        app = _build_app(self.private_dir)
        client = app.test_client()

        env_patch, token_patch, capture_patch = self._patches(status="COMPLETED")
        with env_patch, token_patch, capture_patch:
            resp = client.post(
                "/__fnd/paypal/capture-order",
                data=json.dumps({"order_id": "ORDER_RECEIPT_TEST"}),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("status"), "COMPLETED")
        self.assertIn("receipt_document_url", body)
        self.assertIn("/__fnd/donation/receipt-document", body["receipt_document_url"])
        self.assertIn("receipt_email_status", body)
        # No SES identity configured → skipped (not failed).
        self.assertEqual(body["receipt_email_status"], "skipped")

    def test_capture_response_omits_receipt_url_when_no_artifact(self) -> None:
        _seed_domain_profile(
            self.private_dir,
            domain=self.DOMAIN,
            receipt_artifact_path=None,
        )
        app = _build_app(self.private_dir)
        client = app.test_client()

        env_patch, token_patch, capture_patch = self._patches(status="COMPLETED")
        with env_patch, token_patch, capture_patch:
            resp = client.post(
                "/__fnd/paypal/capture-order",
                data=json.dumps({"order_id": "ORDER_RECEIPT_TEST"}),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body.get("status"), "COMPLETED")
        self.assertNotIn("receipt_document_url", body)
        self.assertNotIn("receipt_email_status", body)

    def test_capture_response_omits_receipt_url_when_not_completed(self) -> None:
        _seed_domain_profile(
            self.private_dir,
            domain=self.DOMAIN,
            receipt_artifact_path=_CVCC_PDF_NAME,
        )
        app = _build_app(self.private_dir)
        client = app.test_client()

        env_patch, token_patch, capture_patch = self._patches(status="PENDING")
        with env_patch, token_patch, capture_patch:
            resp = client.post(
                "/__fnd/paypal/capture-order",
                data=json.dumps({"order_id": "ORDER_RECEIPT_TEST"}),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body.get("status"), "PENDING")
        # Receipt only fulfilled on COMPLETED — pending/declined captures
        # do not earn a receipt link.
        self.assertNotIn("receipt_document_url", body)
        self.assertNotIn("receipt_email_status", body)


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class TestDonateHtmlReceiptInjection(unittest.TestCase):
    """donate.html must (a) carry the receipt-details placeholder that
    the JS overwrites with capture details, and (b) load the canonical
    donate.js extension that owns the receipt-link injection branch.

    Phase 17e moved the receipt-link rendering logic out of inline JS
    on the page and into ``mycite-extensions/donate.js`` so every site
    using ``data-mycite-donate`` gets the same behavior. The string
    ``data.receipt_document_url`` accordingly now lives in donate.js,
    not in donate.html — this test asserts the donate.js load + the
    DOM contract, and a companion check inspects donate.js itself.
    """

    DONATE_HTML = Path(
        "/srv/webapps/clients/cuyahogavalleycountrysideconservancy.org/"
        "frontend/donate.html"
    )
    DONATE_JS = Path(
        "/srv/webapps/clients/_shared/site-core/js/extensions/donate.js"
    )

    @unittest.skipUnless(
        Path(
            "/srv/webapps/clients/cuyahogavalleycountrysideconservancy.org/"
            "frontend/donate.html"
        ).exists(),
        "CVCC donate.html not present in this environment",
    )
    def test_donate_html_loads_donate_js_and_has_receipt_anchor(self) -> None:
        html = self.DONATE_HTML.read_text(encoding="utf-8")
        # The canonical donate.js extension is loaded.
        self.assertIn("mycite-extensions/donate.js", html)
        # The placeholder element the JS replaces with capture details.
        self.assertIn('id="receipt-details"', html)

    @unittest.skipUnless(
        Path(
            "/srv/webapps/clients/_shared/site-core/js/extensions/donate.js"
        ).exists(),
        "donate.js extension not present in this environment",
    )
    def test_donate_js_implements_receipt_download_branch(self) -> None:
        js = self.DONATE_JS.read_text(encoding="utf-8")
        # Server-side response field name + the injected anchor id are
        # owned by donate.js, not the per-site donate.html.
        self.assertIn("data.receipt_document_url", js)
        self.assertIn("receipt-download-link", js)


if __name__ == "__main__":
    unittest.main()
