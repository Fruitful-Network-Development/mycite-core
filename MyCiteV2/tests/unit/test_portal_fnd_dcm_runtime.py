from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_fnd_dcm_runtime import (
    build_portal_fnd_dcm_surface_bundle,
    run_portal_fnd_dcm,
)
from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.packages.state_machine.portal_shell import PortalScope


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_fixture(private_dir: Path, webapps_root: Path) -> None:
    tool_root = private_dir / "utilities" / "tools" / "fnd-dcm"
    tool_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        tool_root / "fnd-dcm.cvcc.json",
        {
            "schema": "mycite.service_tool.fnd_dcm.profile.v1",
            "domain": "cuyahogavalleycountrysideconservancy.org",
            "label": "CVCC",
            "manifest_relative_path": "assets/docs/manifest.json",
            "render_script_relative_path": "scripts/render_manifest.py",
        },
    )
    _write_json(
        tool_root / "fnd-dcm.tff.json",
        {
            "schema": "mycite.service_tool.fnd_dcm.profile.v1",
            "domain": "trappfamilyfarm.com",
            "label": "Trapp Family Farm",
            "manifest_relative_path": "assets/docs/manifest.json",
            "render_script_relative_path": "scripts/render_manifest.py",
        },
    )
    cvcc_root = webapps_root / "clients" / "cuyahogavalleycountrysideconservancy.org" / "frontend"
    tff_root = webapps_root / "clients" / "trappfamilyfarm.com" / "frontend"
    _write_json(
        cvcc_root / "assets" / "docs" / "manifest.json",
        {
            "schema": "webdz.site_content.v2",
            "site": {"name": "CVCC", "homepage_href": "index.html", "shell": {}},
            "navigation": [],
            "footer": {"columns": [{"template": "rich_text"}], "copyright": "©"},
            "collections": {"board_profiles": {"type": "json_file", "source": "assets/docs/board_profiles.json"}},
            "pages": {"people": {"file": "people.html", "template": "board_directory", "content": {"collection": "board_profiles"}}},
        },
    )
    _write_json(cvcc_root / "assets" / "docs" / "board_profiles.json", [{"name": "Jane Example", "bio": ["Jane supports local farming."]}])
    (cvcc_root / "scripts").mkdir(parents=True, exist_ok=True)
    (cvcc_root / "scripts" / "render_manifest.py").write_text("print('ok')\n", encoding="utf-8")
    _write_json(
        tff_root / "assets" / "docs" / "manifest.json",
        {
            "schema": "webdz.site_content.v3",
            "site": {"name": "Trapp Family Farm", "homepage_href": "home.html", "shell": {}},
            "icons": {"favicon": "/favicon.svg"},
            "navigation": [],
            "footer": {"columns": [{"template": "contact_lines"}], "copyright": "©"},
            "collections": {"newsletters": {"type": "markdown_documents", "items": [{"source": "assets/docs/newsletters/fall-2024.md"}]}},
            "pages": {"home": {"file": "home.html", "template": "home_featured"}},
        },
    )
    (tff_root / "assets" / "docs" / "newsletters").mkdir(parents=True, exist_ok=True)
    (tff_root / "assets" / "docs" / "newsletters" / "fall-2024.md").write_text("# Fall\n", encoding="utf-8")
    (tff_root / "scripts").mkdir(parents=True, exist_ok=True)
    (tff_root / "scripts" / "render_manifest.py").write_text("print('ok')\n", encoding="utf-8")


class PortalFndDcmRuntimeTests(unittest.TestCase):
    def test_bundle_defaults_to_cvcc_overview_and_clears_invalid_page(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            webapps_root = root / "webapps"
            _write_fixture(private_dir, webapps_root)

            bundle = build_portal_fnd_dcm_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing", "hosted_site_manifest_visibility")),
                shell_state=None,
                surface_query={"site": "trappfamilyfarm.com", "view": "pages", "page": "people"},
                webapps_root=webapps_root,
                private_dir=private_dir,
                tool_exposure_policy={"configured_tools": {"fnd_dcm": True}, "enabled_tools": {"fnd_dcm": True}},
            )
            default_bundle = build_portal_fnd_dcm_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing", "hosted_site_manifest_visibility")),
                shell_state=None,
                surface_query={},
                webapps_root=webapps_root,
                private_dir=private_dir,
                tool_exposure_policy={"configured_tools": {"fnd_dcm": True}, "enabled_tools": {"fnd_dcm": True}},
            )

            self.assertEqual(bundle["canonical_query"], {"site": "trappfamilyfarm.com", "view": "pages"})
            self.assertEqual(default_bundle["canonical_query"], {"site": "cuyahogavalleycountrysideconservancy.org", "view": "overview"})
            self.assertEqual(default_bundle["surface_payload"]["tool"]["operational"], True)
            self.assertEqual(default_bundle["control_panel"]["surface_label"], "FND-DCM")

    def test_runtime_envelope_stays_visible_but_non_operational_without_webapps_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            webapps_root = root / "webapps"
            _write_fixture(private_dir, webapps_root)

            envelope = run_portal_fnd_dcm(
                {
                    "schema": "mycite.v2.portal.system.tools.fnd_dcm.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                    "surface_query": {"view": "collections", "collection": "board_profiles"},
                },
                webapps_root=root / "missing-webapps",
                private_dir=private_dir,
                tool_exposure_policy={"configured_tools": {"fnd_dcm": True}, "enabled_tools": {"fnd_dcm": True}},
            )

            self.assertEqual(envelope["surface_id"], "system.tools.fnd_dcm")
            self.assertFalse(envelope["reducer_owned"])
            self.assertEqual(envelope["canonical_query"], {"site": "cuyahogavalleycountrysideconservancy.org", "view": "collections"})
            self.assertEqual(envelope["surface_payload"]["tool"]["operational"], False)
            self.assertIn("webapps_root", envelope["surface_payload"]["tool"]["missing_integrations"])
            self.assertEqual(envelope["shell_composition"]["regions"]["workbench"]["kind"], "fnd_dcm_workbench")

    def test_direct_fnd_dcm_endpoint_matches_shell_runtime_envelope(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            webapps_root = root / "webapps"
            _write_fixture(private_dir, webapps_root)

            request_payload = {
                "schema": "mycite.v2.portal.system.tools.fnd_dcm.request.v1",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing", "hosted_site_manifest_visibility"]},
                "surface_query": {"site": "trappfamilyfarm.com", "view": "pages", "page": "home"},
            }
            direct_envelope = run_portal_fnd_dcm(
                request_payload,
                webapps_root=webapps_root,
                private_dir=private_dir,
                tool_exposure_policy={"configured_tools": {"fnd_dcm": True}, "enabled_tools": {"fnd_dcm": True}},
                portal_instance_id="fnd",
                portal_domain="trappfamilyfarm.com",
            )
            shell_envelope = run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.tools.fnd_dcm",
                    "portal_scope": request_payload["portal_scope"],
                    "surface_query": request_payload["surface_query"],
                },
                portal_instance_id="fnd",
                portal_domain="trappfamilyfarm.com",
                webapps_root=webapps_root,
                private_dir=private_dir,
                tool_exposure_policy={"configured_tools": {"fnd_dcm": True}, "enabled_tools": {"fnd_dcm": True}},
            )

            self.assertEqual(direct_envelope["surface_id"], shell_envelope["surface_id"])
            self.assertEqual(direct_envelope["reducer_owned"], shell_envelope["reducer_owned"])
            self.assertEqual(direct_envelope["canonical_query"], shell_envelope["canonical_query"])
            self.assertEqual(direct_envelope["canonical_url"], shell_envelope["canonical_url"])
            self.assertEqual(direct_envelope["shell_composition"], shell_envelope["shell_composition"])
            self.assertEqual(
                direct_envelope["surface_payload"]["workspace"]["canonical_query"],
                shell_envelope["surface_payload"]["workspace"]["canonical_query"],
            )


if __name__ == "__main__":
    unittest.main()
