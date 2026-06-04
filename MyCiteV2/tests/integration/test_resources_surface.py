"""Wave-1 scaffold — top-level Resources surface (site-core gallery listing).

The Resources root surface (``resources.root`` → ``/portal/resources``)
lists the shared site-core galleries read-only, one subtab per gallery:
profiles / icon / image / document / audio / events / contacts.

These tests pin the scaffold contract:

  1. ``build_resources_surface_payload`` against a temp webapps_root with
     a couple of fake gallery files returns correct counts and tolerates a
     missing ``events/`` directory (empty subtab, not an error).
  2. For PII galleries (events, contacts) only filenames/counts are
     listed — file CONTENTS are never read or exposed.
  3. ``GET /portal/resources`` returns 200.
  4. The runtime bundle for the resources surface (the payload the shell
     API serves) carries the gallery subtabs.

Rich per-gallery UX (contact-app, icon dedup, editing, upload) is Wave 2.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.instances._shared.runtime.utilities_extensions.resources_surface import (
    RESOURCE_GALLERIES,
    build_resources_surface_payload,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    PORTAL_SHELL_REQUEST_SCHEMA,
    RESOURCES_ROOT_SURFACE_ID,
    PortalScope,
)


def _seed_site_core(webapps_root: Path) -> Path:
    site_core = webapps_root / "clients" / "_shared" / "site-core"
    (site_core / "icon").mkdir(parents=True)
    (site_core / "icon" / "logo.svg").write_text("<svg/>", encoding="utf-8")
    (site_core / "icon" / "mark.png").write_text("pngbytes", encoding="utf-8")
    (site_core / "profiles").mkdir()
    (site_core / "profiles" / "alpha.json").write_text("{}", encoding="utf-8")
    # contacts is a PII gallery — seed a file to confirm contents stay hidden.
    (site_core / "contacts").mkdir()
    (site_core / "contacts" / "leads.json").write_text(
        '{"email":"secret@example.test"}', encoding="utf-8"
    )
    # events/ deliberately NOT created → must tolerate the missing dir.
    return webapps_root


class ResourcesSurfaceBuilderTests(unittest.TestCase):
    def test_counts_and_missing_dir_tolerated(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="resources_builder_"))
        _seed_site_core(tmp)
        payload = build_resources_surface_payload(tmp)

        self.assertEqual(payload["kind"], "resources")
        by_gallery = {sub["gallery"]: sub for sub in payload["subtabs"]}
        # All declared galleries present as subtabs, in declared order.
        self.assertEqual(
            [sub["gallery"] for sub in payload["subtabs"]],
            [spec["gallery"] for spec in RESOURCE_GALLERIES],
        )
        self.assertEqual(by_gallery["icon"]["count"], 2)
        self.assertTrue(by_gallery["icon"]["exists"])
        self.assertEqual(by_gallery["profiles"]["count"], 1)
        # Missing events/ → empty subtab, not an error.
        self.assertEqual(by_gallery["events"]["count"], 0)
        self.assertFalse(by_gallery["events"]["exists"])
        self.assertEqual(by_gallery["events"]["entries"], [])

    def test_pii_galleries_expose_no_file_contents(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="resources_pii_"))
        _seed_site_core(tmp)
        payload = build_resources_surface_payload(tmp)
        by_gallery = {sub["gallery"]: sub for sub in payload["subtabs"]}
        contacts = by_gallery["contacts"]
        self.assertTrue(contacts["pii"])
        self.assertEqual(contacts["count"], 1)
        for entry in contacts["entries"]:
            # Only filename + cheap metadata — never the file body.
            self.assertEqual(
                set(entry.keys()), {"filename", "extension", "size_bytes"}
            )
            for value in entry.values():
                self.assertNotIn("secret@example.test", str(value))

    def test_none_webapps_root_tolerated(self) -> None:
        payload = build_resources_surface_payload(None)
        self.assertEqual(payload["kind"], "resources")
        self.assertEqual(len(payload["subtabs"]), len(RESOURCE_GALLERIES))
        for sub in payload["subtabs"]:
            self.assertEqual(sub["count"], 0)
            self.assertFalse(sub["exists"])


class ResourcesSurfaceRuntimeTests(unittest.TestCase):
    def test_runtime_bundle_carries_gallery_subtabs(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="resources_runtime_"))
        _seed_site_core(tmp)
        request = {
            "schema": PORTAL_SHELL_REQUEST_SCHEMA,
            "requested_surface_id": RESOURCES_ROOT_SURFACE_ID,
            "portal_scope": PortalScope(scope_id="fnd", capabilities=()).to_dict(),
        }
        envelope = run_portal_shell_entry(
            request,
            portal_instance_id="fnd",
            portal_domain="example.test",
            webapps_root=tmp,
        )
        surface_payload = envelope["surface_payload"]
        self.assertEqual(surface_payload["kind"], "resources")
        galleries = {sub["gallery"] for sub in surface_payload["subtabs"]}
        self.assertEqual(
            galleries, {spec["gallery"] for spec in RESOURCE_GALLERIES}
        )
        by_gallery = {sub["gallery"]: sub for sub in surface_payload["subtabs"]}
        self.assertEqual(by_gallery["icon"]["count"], 2)


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class ResourcesSurfaceRouteTests(unittest.TestCase):
    def _make_app(self):
        from MyCiteV2.instances._shared.portal_host.app import (
            V2PortalHostConfig,
            create_app,
        )

        tmp = Path(tempfile.mkdtemp(prefix="resources_route_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        _seed_site_core(tmp / "webapps")
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return create_app(config)

    def test_get_resources_returns_200(self) -> None:
        app = self._make_app()
        client = app.test_client()
        response = client.get("/portal/resources")
        self.assertEqual(response.status_code, 200)
        # The shell HTML bootstraps the resources surface request.
        self.assertIn(RESOURCES_ROOT_SURFACE_ID, response.get_data(as_text=True))

    def test_shell_api_serves_gallery_subtabs(self) -> None:
        app = self._make_app()
        client = app.test_client()
        response = client.post(
            "/portal/api/v2/shell",
            json={
                "schema": PORTAL_SHELL_REQUEST_SCHEMA,
                "requested_surface_id": RESOURCES_ROOT_SURFACE_ID,
                "portal_scope": PortalScope(
                    scope_id="fnd", capabilities=()
                ).to_dict(),
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        # The serialized payload names every gallery subtab.
        for spec in RESOURCE_GALLERIES:
            self.assertIn(spec["gallery"], body)


if __name__ == "__main__":
    unittest.main()
