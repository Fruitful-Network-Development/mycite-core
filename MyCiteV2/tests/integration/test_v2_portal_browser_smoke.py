from __future__ import annotations

import json
import sys
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from flask import Flask
    from werkzeug.serving import make_server

    HAS_FLASK = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]
    make_server = None  # type: ignore[assignment]

try:
    from playwright.sync_api import sync_playwright

    HAS_PLAYWRIGHT = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_PLAYWRIGHT = False
    sync_playwright = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if HAS_FLASK:
    from MyCiteV2.instances._shared.portal_host import V2PortalHostConfig, create_app
else:  # pragma: no cover
    V2PortalHostConfig = object  # type: ignore[assignment]
    create_app = None  # type: ignore[assignment]


def _build_config(temp_root: Path, *, tenant_id: str = "fnd", cts_gis_enabled: bool = False) -> V2PortalHostConfig:
    public_dir = temp_root / "public"
    private_dir = temp_root / "private"
    data_dir = temp_root / "data"
    webapps_root = temp_root / "webapps"
    (data_dir / "system" / "sources").mkdir(parents=True)
    (data_dir / "payloads" / "cache").mkdir(parents=True)
    public_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True)
    (private_dir / "local_audit").mkdir(parents=True)
    webapps_root.mkdir(parents=True)
    (data_dir / "system" / "anthology.json").write_text("{}\n", encoding="utf-8")
    (data_dir / "system" / "sources" / "sc.example.json").write_text("{}\n", encoding="utf-8")
    (data_dir / "payloads" / "cache" / "sc.example.txa.json").write_text("{}\n", encoding="utf-8")
    (public_dir / "msn-example.json").write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    (private_dir / "config.json").write_text(
        json.dumps(
            {
                "tools_configuration": [],
                "tool_exposure": {
                    "aws": {"enabled": True},
                    "aws_csm_newsletter": {"enabled": False},
                    "aws_narrow_write": {"enabled": True},
                    "aws_csm_onboarding": {"enabled": True},
                    "aws_csm_sandbox": {"enabled": False},
                    "cts_gis": {"enabled": cts_gis_enabled},
                    "fnd_ebi": {"enabled": False},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    aws_status_file = temp_root / "aws-csm.fnd.technicalContact.json"
    aws_status_file.write_text(
        json.dumps(
            {
                "schema": "mycite.service_tool.aws_csm.profile.v1",
                "identity": {
                    "profile_id": "aws-csm.fnd.technicalContact",
                    "tenant_id": tenant_id,
                    "domain": "fruitfulnetworkdevelopment.com",
                    "mailbox_local_part": "technicalcontact",
                    "send_as_email": "technicalcontact@fruitfulnetworkdevelopment.com",
                },
                "smtp": {"handoff_ready": True, "credentials_secret_state": "configured"},
                "verification": {"status": "verified"},
                "provider": {"gmail_send_as_status": "verified"},
                "workflow": {
                    "initiated": True,
                    "lifecycle_state": "operational",
                    "is_ready_for_user_handoff": True,
                    "is_mailbox_operational": True,
                },
                "inbound": {"receive_verified": True, "receive_state": "receive_operational"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return V2PortalHostConfig(
        tenant_id=tenant_id,
        public_dir=public_dir,
        private_dir=private_dir,
        data_dir=data_dir,
        analytics_domain="fruitfulnetworkdevelopment.com",
        analytics_webapps_root=webapps_root,
        aws_status_file=aws_status_file,
        aws_audit_storage_file=private_dir / "local_audit" / "aws.ndjson",
        admin_audit_storage_file=private_dir / "local_audit" / "admin.ndjson",
    )


@contextmanager
def _serve_app(app: Flask):
    server = make_server("127.0.0.1", 0, app)
    host, port = server.socket.getsockname()[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@unittest.skipUnless(HAS_FLASK and HAS_PLAYWRIGHT, "browser smoke tests require Flask and Playwright")
class V2PortalBrowserSmokeTests(unittest.TestCase):
    def test_system_page_hydrates_and_syncs_theme_selectors(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app = create_app(_build_config(Path(temp_dir)))
            with _serve_app(app) as base_url:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    page = browser.new_page()
                    try:
                        page.goto(base_url + "/portal/system", wait_until="networkidle")
                        page.wait_for_function("document.body.getAttribute('data-shell-boot-state') === 'hydrated'")
                        self.assertEqual(
                            page.locator("[data-theme-selector]").count(),
                            2,
                        )
                        values = page.locator("[data-theme-selector]").evaluate_all(
                            "(nodes) => nodes.map((node) => ({value: node.value, size: node.options.length}))"
                        )
                        self.assertEqual(values[0]["value"], values[1]["value"])
                        self.assertEqual(values[0]["size"], values[1]["size"])
                        self.assertNotIn(
                            "Loading shell regions from the runtime",
                            page.locator("#portalControlPanel").inner_text(),
                        )
                        self.assertGreater(page.locator("#v2-activity-nav a").count(), 0)
                    finally:
                        browser.close()

    def test_cts_gis_route_opens_interface_panel_primary(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app = create_app(_build_config(Path(temp_dir), cts_gis_enabled=True))
            with _serve_app(app) as base_url:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    page = browser.new_page()
                    try:
                        page.goto(base_url + "/portal/utilities/cts-gis", wait_until="networkidle")
                        page.wait_for_function("document.body.getAttribute('data-shell-boot-state') === 'hydrated'")
                        self.assertEqual(
                            page.locator(".ide-shell").get_attribute("data-foreground-shell-region"),
                            "interface-panel",
                        )
                        self.assertEqual(
                            page.locator("#portalInspector").get_attribute("data-primary-surface"),
                            "true",
                        )
                        self.assertEqual(
                            page.locator("#portalInspector [data-cts-gis-interface-panel='true']").count(),
                            1,
                        )
                        self.assertGreater(
                            page.locator("#portalInspector [data-cts-gis-geojson-lens='true'] svg").count(),
                            0,
                        )
                        self.assertEqual(
                            page.locator("[data-shell-region='center-workbench'] [data-cts-gis-evidence-workbench='true']").count(),
                            1,
                        )
                        self.assertIn(
                            "Raw datum underlay",
                            page.locator("[data-shell-region='center-workbench']").inner_text(),
                        )
                    finally:
                        browser.close()

    def test_shell_post_failure_enters_fatal_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app = create_app(_build_config(Path(temp_dir)))
            with _serve_app(app) as base_url:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    page = browser.new_page()
                    page.route(
                        "**/portal/api/v2/admin/shell",
                        lambda route: route.fulfill(status=503, body="shell unavailable"),
                    )
                    try:
                        page.goto(base_url + "/portal/system", wait_until="domcontentloaded")
                        page.wait_for_function("document.body.getAttribute('data-shell-boot-state') === 'fatal'")
                        self.assertIn("shell failed", page.locator("#portalControlPanel").inner_text().lower())
                    finally:
                        browser.close()

    def test_bundle_failure_watchdog_enters_fatal_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app = create_app(_build_config(Path(temp_dir)))
            with _serve_app(app) as base_url:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    page = browser.new_page()
                    page.route(
                        "**/portal/static/v2_portal_shell_core.js",
                        lambda route: route.abort(),
                    )
                    try:
                        page.goto(base_url + "/portal/system", wait_until="domcontentloaded")
                        page.wait_for_function("document.body.getAttribute('data-shell-boot-state') === 'fatal'")
                        self.assertIn("did not load", page.locator("#portalControlPanel").inner_text().lower())
                    finally:
                        browser.close()


if __name__ == "__main__":
    unittest.main()
