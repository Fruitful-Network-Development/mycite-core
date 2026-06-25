"""Phase 14b — four dedicated Utilities surfaces.

The single ``/portal/utilities/tool-exposure`` surface (which conflated
extensions + tools + grantee profile + workbench_ui) is replaced by
four per-purpose surfaces:

  * ``/portal/utilities/extensions``      — operational extensions only
  * ``/portal/utilities/grantee-profile`` — grantee selector + editor
  * ``/portal/utilities/tools``           — tool posture (CTS-GIS etc.)
  * ``/portal/utilities/peripherals``     — keypass vault + peripherals (stub)

These tests pin the contract of each surface independently.
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

from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA
from MyCiteV2.packages.state_machine.portal_shell import (
    PORTAL_SHELL_REQUEST_SCHEMA,
    UTILITIES_PERIPHERALS_SURFACE_ID,
    UTILITIES_TOOLS_SURFACE_ID,
)

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app


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


def _build_tempdirs() -> tuple[Path, Path, Path, Path]:
    root = Path(tempfile.mkdtemp(prefix="phase14b_surface_"))
    for sub in ("public", "private", "data", "webapps"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    _seed_grantee(
        root / "private" / "utilities" / "tools" / "fnd-csm",
        "alpha",
        "Alpha Grantee",
        ["alpha.example.test"],
    )
    return root / "public", root / "private", root / "data", root / "webapps"


def _surface_payload(surface_id: str) -> dict:
    public_dir, private_dir, data_dir, webapps_root = _build_tempdirs()
    response = run_portal_shell_entry(
        {"schema": PORTAL_SHELL_REQUEST_SCHEMA, "requested_surface_id": surface_id},
        portal_instance_id="fnd",
        portal_domain="example.test",
        public_dir=public_dir,
        private_dir=private_dir,
        data_dir=data_dir,
        webapps_root=webapps_root,
    )
    return response.get("surface_payload", {})


class UtilitiesToolsSurfaceTests(unittest.TestCase):
    def test_tools_surface_excludes_extensions_and_workbench_ui(self) -> None:
        payload = _surface_payload(UTILITIES_TOOLS_SURFACE_ID)
        self.assertEqual(payload.get("kind"), "tools")
        rows = []
        for section in payload.get("sections") or []:
            rows.extend(section.get("items") or [])
        tool_labels = {row.get("tool") for row in rows}
        # Should contain a palette tool (Agro-ERP; CTS-GIS retired in Stage C);
        # never any extension or workbench_ui.
        self.assertIn("Agro-ERP", tool_labels)
        self.assertNotIn("CTS-GIS", tool_labels)
        for forbidden in ("Email", "Analytics", "Newsletter", "PayPal", "Grantee Profile", "Workbench UI"):
            self.assertNotIn(
                forbidden,
                tool_labels,
                f"tools surface unexpectedly contains {forbidden!r}",
            )


class UtilitiesPeripheralsSurfaceTests(unittest.TestCase):
    def test_peripherals_surface_renders_stub_cards(self) -> None:
        payload = _surface_payload(UTILITIES_PERIPHERALS_SURFACE_ID)
        self.assertEqual(payload.get("kind"), "peripherals")
        card_labels = {card.get("label") for card in payload.get("cards") or []}
        self.assertIn("Keypass vault", card_labels)


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class UtilitiesLegacyRedirectsTests(unittest.TestCase):
    def _build_app(self):
        tmp = Path(tempfile.mkdtemp(prefix="phase14b_redirect_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client()

    def test_tool_exposure_route_redirects_to_utilities(self) -> None:
        client = self._build_app()
        resp = client.get("/portal/utilities/tool-exposure", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], "/portal/utilities")

    def test_integrations_route_redirects_to_peripherals(self) -> None:
        client = self._build_app()
        resp = client.get("/portal/utilities/integrations", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], "/portal/utilities/peripherals")


if __name__ == "__main__":
    unittest.main()
