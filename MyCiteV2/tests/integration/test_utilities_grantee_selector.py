"""Phase 12h integration test for the surface-level grantee selector.

Per the Phase 12 plan, the utilities tool-exposure surface emits a
top-level `grantee_selector` payload listing every available grantee.
Switching grantees is done by POSTing a shell request with
`surface_query.selected_grantee_msn` set; the next GET shows the new
grantee as active and the extension payloads reflect its data.

Without this selector, operators have to edit URL query parameters or
rely on the first-by-label-alphabetical default that
`_resolve_selected_grantee` falls back to.
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
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA
from MyCiteV2.packages.state_machine.portal_shell import (
    PORTAL_SHELL_REQUEST_SCHEMA,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
)


def _seed_grantee(grantee_dir: Path, msn_id: str, label: str, domains: list) -> None:
    grantee_dir.mkdir(parents=True, exist_ok=True)
    path = grantee_dir / f"grantee.fnd-msn.{msn_id}.json"
    path.write_text(
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


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed")
class UtilitiesGranteeSelectorTests(unittest.TestCase):
    def _build_tempdirs(self):
        root = Path(tempfile.mkdtemp(prefix="phase12h_selector_"))
        for sub in ("public", "private", "data", "webapps"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        return root / "public", root / "private", root / "data", root / "webapps"

    def _surface_payload(self, *, public_dir, private_dir, data_dir, webapps_root, surface_query=None):
        request = {
            "schema": PORTAL_SHELL_REQUEST_SCHEMA,
            "requested_surface_id": UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
        }
        if surface_query is not None:
            request["surface_query"] = surface_query
        response = run_portal_shell_entry(
            request,
            portal_instance_id="fnd",
            portal_domain="example.org",
            public_dir=public_dir,
            private_dir=private_dir,
            data_dir=data_dir,
            webapps_root=webapps_root,
        )
        return response.get("surface_payload", {})

    def test_grantee_selector_present_on_surface(self) -> None:
        public_dir, private_dir, data_dir, webapps_root = self._build_tempdirs()
        grantee_dir = private_dir / "utilities" / "tools" / "fnd-csm"
        _seed_grantee(grantee_dir, "g1", "Alpha Grantee", ["alpha.org"])
        _seed_grantee(grantee_dir, "g2", "Beta Grantee", ["beta.org"])

        payload = self._surface_payload(
            public_dir=public_dir,
            private_dir=private_dir,
            data_dir=data_dir,
            webapps_root=webapps_root,
        )
        self.assertIn("grantee_selector", payload)
        selector = payload["grantee_selector"]
        self.assertEqual(selector["label"], "Grantee")
        # The list now leads with a synthetic "All — Overall" entry (engages the
        # global view); the real grantees follow.
        self.assertTrue(selector["grantees"][0].get("is_overall"))
        listed_msns = [
            g["msn_id"] for g in selector["grantees"] if not g.get("is_overall")
        ]
        self.assertEqual(sorted(listed_msns), ["g1", "g2"])

    def test_one_grantee_is_marked_active_by_default(self) -> None:
        public_dir, private_dir, data_dir, webapps_root = self._build_tempdirs()
        grantee_dir = private_dir / "utilities" / "tools" / "fnd-csm"
        _seed_grantee(grantee_dir, "g1", "Alpha Grantee", ["alpha.org"])
        _seed_grantee(grantee_dir, "g2", "Beta Grantee", ["beta.org"])

        payload = self._surface_payload(
            public_dir=public_dir,
            private_dir=private_dir,
            data_dir=data_dir,
            webapps_root=webapps_root,
        )
        selector = payload["grantee_selector"]
        active = [g for g in selector["grantees"] if g["active"]]
        self.assertEqual(
            len(active),
            1,
            f"exactly one grantee should be active by default; got {[g['msn_id'] for g in active]}",
        )
        self.assertEqual(selector["selected_grantee_msn"], active[0]["msn_id"])

    def test_surface_query_selected_grantee_msn_overrides_default(self) -> None:
        public_dir, private_dir, data_dir, webapps_root = self._build_tempdirs()
        grantee_dir = private_dir / "utilities" / "tools" / "fnd-csm"
        _seed_grantee(grantee_dir, "g1", "Alpha Grantee", ["alpha.org"])
        _seed_grantee(grantee_dir, "g2", "Beta Grantee", ["beta.org"])

        payload = self._surface_payload(
            public_dir=public_dir,
            private_dir=private_dir,
            data_dir=data_dir,
            webapps_root=webapps_root,
            surface_query={"selected_grantee_msn": "g2"},
        )
        selector = payload["grantee_selector"]
        self.assertEqual(selector["selected_grantee_msn"], "g2")
        active = [g for g in selector["grantees"] if g["active"]]
        self.assertEqual([g["msn_id"] for g in active], ["g2"])

    def test_select_action_dispatches_through_shell_with_updated_query(self) -> None:
        public_dir, private_dir, data_dir, webapps_root = self._build_tempdirs()
        grantee_dir = private_dir / "utilities" / "tools" / "fnd-csm"
        _seed_grantee(grantee_dir, "g1", "Alpha Grantee", ["alpha.org"])

        payload = self._surface_payload(
            public_dir=public_dir,
            private_dir=private_dir,
            data_dir=data_dir,
            webapps_root=webapps_root,
        )
        selector = payload["grantee_selector"]
        first = selector["grantees"][0]
        action = first["select_action"]
        self.assertEqual(action["route"], "/portal/api/v2/shell")
        self.assertEqual(
            action["payload"]["requested_surface_id"],
            "utilities.tool_exposure",
        )
        self.assertEqual(
            action["payload"]["surface_query"]["selected_grantee_msn"],
            first["msn_id"],
        )

    def test_empty_grantee_dir_yields_empty_selector_list_with_help_text(self) -> None:
        public_dir, private_dir, data_dir, webapps_root = self._build_tempdirs()
        payload = self._surface_payload(
            public_dir=public_dir,
            private_dir=private_dir,
            data_dir=data_dir,
            webapps_root=webapps_root,
        )
        selector = payload["grantee_selector"]
        self.assertEqual(selector["grantees"], [])
        self.assertIn("grantee", selector["empty_message"].lower())


if __name__ == "__main__":
    unittest.main()
