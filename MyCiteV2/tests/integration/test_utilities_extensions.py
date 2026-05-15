"""Phase 2 integration tests for the Utilities tool-exposure extension surface.

Tests:
  - the four extension entries register and appear in the registry
  - the tool-exposure surface payload exposes a structured ``extensions`` list
  - the PayPal extension picks up rows from orders.ndjson
  - the legacy /portal/system/tools/fnd-csm route 302-redirects to Utilities

See portal_tool_surface_contract.md and the approved plan
/home/admin/.claude/plans/temporal-wandering-bengio.md (Phase 2).
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
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

from MyCiteV2.packages.state_machine.portal_shell import (
    PORTAL_SHELL_REQUEST_SCHEMA,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    build_portal_tool_registry_entries,
)

EXPECTED_EXTENSION_IDS = (
    "ext_aws_email",
    "ext_analytics",
    "ext_newsletter",
    "ext_paypal",
    # Phase 17b: the Connect extension joins the 4 operational
    # extensions on the Utilities/Extensions surface.
    "ext_connect",
    # Phase 9 (grantee_profile_contract.md): grantee profile editor lives
    # under its own utilities.grantee_profile surface alongside the
    # operational extensions tab strip.
    "ext_grantee_profile",
)


class TestExtensionRegistry(unittest.TestCase):
    def test_all_extensions_register_under_utilities(self) -> None:
        entries = build_portal_tool_registry_entries()
        extension_entries = {e.tool_id: e for e in entries if e.is_extension}
        self.assertEqual(set(extension_entries.keys()), set(EXPECTED_EXTENSION_IDS))
        # Phase 14b split: the four operational extensions (Email,
        # Analytics, Newsletter, PayPal) live on ``utilities.extensions``;
        # the ext_grantee_profile form is hosted by its own dedicated
        # ``utilities.grantee_profile`` surface.
        for tool_id, entry in extension_entries.items():
            expected_surface = (
                "utilities.grantee_profile"
                if tool_id == "ext_grantee_profile"
                else "utilities.extensions"
            )
            self.assertEqual(
                entry.surface_id,
                expected_surface,
                f"{tool_id} must register under {expected_surface}",
            )
            self.assertEqual(entry.surface_posture, "palette_target")


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class TestUtilitiesToolExposureSurface(unittest.TestCase):
    def _build_tempdirs(self) -> tuple[Path, Path, Path, Path]:
        root = Path(tempfile.mkdtemp(prefix="phase2_utilities_"))
        for sub in ("public", "private", "data", "webapps"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        return root / "public", root / "private", root / "data", root / "webapps"

    def test_utilities_tool_exposure_lists_all_extensions(self) -> None:
        public_dir, private_dir, data_dir, webapps_root = self._build_tempdirs()
        response = run_portal_shell_entry(
            {
                "schema": PORTAL_SHELL_REQUEST_SCHEMA,
                "requested_surface_id": UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
            },
            portal_instance_id="fnd",
            portal_domain="example.org",
            public_dir=public_dir,
            private_dir=private_dir,
            data_dir=data_dir,
            webapps_root=webapps_root,
        )
        surface_payload = response.get("surface_payload", {})
        self.assertEqual(surface_payload.get("kind"), "tool_exposure")
        extensions = surface_payload.get("extensions", [])
        tool_ids = [ext.get("tool_id") for ext in extensions]
        self.assertEqual(sorted(tool_ids), sorted(EXPECTED_EXTENSION_IDS))
        for ext in extensions:
            self.assertIn("payload", ext)
            self.assertIn("label", ext)
            self.assertIn("summary", ext)

    def test_paypal_extension_renders_orders_ndjson(self) -> None:
        public_dir, private_dir, data_dir, webapps_root = self._build_tempdirs()

        # Seed a single order in the PayPal NDJSON store at the legacy location
        # that _build_paypal_extension_payload reads.
        paypal_dir = private_dir / "utilities" / "tools" / "paypal-csm"
        paypal_dir.mkdir(parents=True, exist_ok=True)
        order_row = {
            "order_id": "ORD-TEST-001",
            "amount": "5.00",
            "currency": "USD",
            "domain": "cuyahogavalleycountrysideconservancy.org",
            "captured": False,
            "created_at": "2026-05-14T00:00:00Z",
        }
        (paypal_dir / "orders.ndjson").write_text(
            json.dumps(order_row) + "\n", encoding="utf-8"
        )

        # Seed a grantee profile so the resolver picks a domain.
        fnd_csm_dir = private_dir / "utilities" / "tools" / "fnd-csm"
        fnd_csm_dir.mkdir(parents=True, exist_ok=True)
        (fnd_csm_dir / "grantee.fnd.cvcc.json").write_text(
            json.dumps(
                {
                    "schema": "mycite.v2.grantee.profile.v1",
                    "msn_id": "fnd.cvcc",
                    "label": "CVCC Board",
                    "short_name": "cvcc",
                    "domains": ["cuyahogavalleycountrysideconservancy.org"],
                    "users": [],
                }
            ),
            encoding="utf-8",
        )

        response = run_portal_shell_entry(
            {
                "schema": PORTAL_SHELL_REQUEST_SCHEMA,
                "requested_surface_id": UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
            },
            portal_instance_id="fnd",
            portal_domain="example.org",
            public_dir=public_dir,
            private_dir=private_dir,
            data_dir=data_dir,
            webapps_root=webapps_root,
        )
        extensions = response.get("surface_payload", {}).get("extensions", [])
        paypal_ext = next(
            (e for e in extensions if e["tool_id"] == "ext_paypal"), None
        )
        self.assertIsNotNone(paypal_ext, "ext_paypal must be present in extensions list")
        orders = paypal_ext["payload"].get("orders", [])
        order_ids = [o.get("order_id") for o in orders]
        self.assertIn(
            "ORD-TEST-001",
            order_ids,
            f"Seeded orders.ndjson row must surface in PayPal extension payload; got orders={orders}",
        )

    def test_fnd_csm_legacy_route_redirects_to_utilities(self) -> None:
        public_dir, private_dir, data_dir, webapps_root = self._build_tempdirs()
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=public_dir,
            private_dir=private_dir,
            data_dir=data_dir,
            portal_domain="example.org",
            webapps_root=webapps_root,
        )
        app = create_app(config)
        client = app.test_client()
        resp = client.get("/portal/system/tools/fnd-csm", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], "/portal/utilities/tool-exposure")


if __name__ == "__main__":
    unittest.main()
