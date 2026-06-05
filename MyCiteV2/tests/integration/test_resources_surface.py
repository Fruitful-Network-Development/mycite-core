"""Resources gallery-listing builder (the read half of ext_resources).

Wave 2 RETIRED the Wave-1 ``resources.root`` top-level surface and re-homed
resources as the ``ext_resources`` Utilities extension. These tests pin the
gallery-listing builder that still backs the extension's gallery counts:

  1. ``build_resources_surface_payload`` against a temp webapps_root returns
     correct per-gallery counts and tolerates a missing ``events/`` dir.
  2. For PII galleries (events, contacts) only filenames/counts are listed —
     file CONTENTS are never read or exposed.
  3. The retired root surface is GONE: ``resources.root`` is no longer in the
     surface catalog and ``/portal/resources`` is no longer a root route.

The extension itself (profiles contact-app, save/derive round-trip, icon
dedup, manifest-add) is covered by ``test_resources_extension.py``.
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

from MyCiteV2.instances._shared.runtime.utilities_extensions.resources_surface import (
    RESOURCE_GALLERIES,
    build_resources_surface_payload,
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


class ResourcesGalleryBuilderTests(unittest.TestCase):
    def test_counts_and_missing_dir_tolerated(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="resources_builder_"))
        _seed_site_core(tmp)
        payload = build_resources_surface_payload(tmp)

        self.assertEqual(payload["kind"], "resources")
        by_gallery = {sub["gallery"]: sub for sub in payload["subtabs"]}
        self.assertEqual(
            [sub["gallery"] for sub in payload["subtabs"]],
            [spec["gallery"] for spec in RESOURCE_GALLERIES],
        )
        self.assertEqual(by_gallery["icon"]["count"], 2)
        self.assertTrue(by_gallery["icon"]["exists"])
        self.assertEqual(by_gallery["profiles"]["count"], 1)
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
            self.assertEqual(set(entry.keys()), {"filename", "extension", "size_bytes"})
            for value in entry.values():
                self.assertNotIn("secret@example.test", str(value))

    def test_none_webapps_root_tolerated(self) -> None:
        payload = build_resources_surface_payload(None)
        self.assertEqual(payload["kind"], "resources")
        self.assertEqual(len(payload["subtabs"]), len(RESOURCE_GALLERIES))
        for sub in payload["subtabs"]:
            self.assertEqual(sub["count"], 0)
            self.assertFalse(sub["exists"])


class ResourcesRootSurfaceRetiredTests(unittest.TestCase):
    """The Wave-1 root surface must be fully gone — resources is an extension."""

    def test_resources_root_not_in_surface_catalog(self) -> None:
        from MyCiteV2.packages.state_machine.portal_shell.shell_registry import (
            build_portal_surface_catalog,
        )

        surface_ids = {e.surface_id for e in build_portal_surface_catalog()}
        self.assertNotIn("resources.root", surface_ids)

    def test_resources_root_symbols_removed_from_schemas(self) -> None:
        from MyCiteV2.packages.state_machine.portal_shell import shell_schemas

        self.assertFalse(hasattr(shell_schemas, "RESOURCES_ROOT_SURFACE_ID"))
        self.assertFalse(hasattr(shell_schemas, "RESOURCES_ROOT_ROUTE"))
        self.assertNotIn("resources.root", shell_schemas.ROOT_SURFACE_IDS)

    @unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
    def test_portal_resources_route_gone_and_healthz_clean(self) -> None:
        from MyCiteV2.instances._shared.portal_host.app import (
            V2PortalHostConfig,
            create_app,
        )

        tmp = Path(tempfile.mkdtemp(prefix="resources_retired_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        _seed_site_core(tmp / "webapps")
        app = create_app(
            V2PortalHostConfig(
                portal_instance_id="fnd",
                public_dir=tmp / "public",
                private_dir=tmp / "private",
                data_dir=tmp / "data",
                portal_domain="example.test",
                webapps_root=tmp / "webapps",
            )
        )
        client = app.test_client()
        self.assertEqual(client.get("/portal/resources").status_code, 404)
        healthz = client.get("/portal/healthz").get_json()
        self.assertNotIn("/portal/resources", healthz.get("root_routes", []))


if __name__ == "__main__":
    unittest.main()
