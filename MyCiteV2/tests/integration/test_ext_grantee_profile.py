"""Phase 9 integration tests for ext_grantee_profile + POST /__fnd/grantee/save.

Covers:
  - ext_grantee_profile is registered as a fifth utilities extension
  - the extension renderer returns a form_component_frame with the
    expected field set (15 fields covering identity + 3 sub-configs)
  - the renderer handles "no grantee selected" gracefully
  - POST /__fnd/grantee/save with valid identity changes round-trips to disk
  - dotted-key fields (paypal.webhook_url etc.) deserialize into nested
    GranteeProfile sub-configs
  - bad payloads return 4xx with a structured error
  - validation failures surface a useful detail message
  - the grantee file remains uncorrupted on validation failure (no torn
    write — the atomic save_grantee_profile guarantees this)
  - the surface payload at /portal/utilities/tool-exposure surfaces the
    new extension alongside the original four
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

from MyCiteV2.instances._shared.runtime.utilities_extensions import (
    EXTENSION_RENDERERS,
    _render_ext_grantee_profile,
)
from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA
from MyCiteV2.packages.state_machine.portal_shell import (
    PORTAL_SHELL_REQUEST_SCHEMA,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    build_portal_tool_registry_entries,
)


def _seed_grantee(grantee_dir: Path, msn_id: str, *, label: str = "Test Grantee") -> Path:
    grantee_dir.mkdir(parents=True, exist_ok=True)
    path = grantee_dir / f"grantee.fnd-msn.{msn_id}.json"
    path.write_text(
        json.dumps(
            {
                "schema": GRANTEE_PROFILE_SCHEMA,
                "msn_id": msn_id,
                "label": label,
                "short_name": msn_id,
                "domains": ["example.org"],
                "users": ["alice@example.org"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


class GranteeProfileExtensionRegistryTests(unittest.TestCase):
    def test_registry_includes_ext_grantee_profile(self) -> None:
        tool_ids = [e.tool_id for e in build_portal_tool_registry_entries()]
        self.assertIn("ext_grantee_profile", tool_ids)

    def test_extension_registers_with_correct_metadata(self) -> None:
        entry = next(
            e for e in build_portal_tool_registry_entries() if e.tool_id == "ext_grantee_profile"
        )
        self.assertTrue(entry.is_extension)
        # Phase 14b: ext_grantee_profile moved off the legacy
        # ``utilities.tool_exposure`` and onto its own dedicated
        # ``utilities.grantee_profile`` surface.
        self.assertEqual(entry.surface_id, "utilities.grantee_profile")
        self.assertEqual(entry.read_write_posture, "write")

    def test_dispatch_table_routes_grantee_profile(self) -> None:
        self.assertIn("ext_grantee_profile", EXTENSION_RENDERERS)


class GranteeProfileRendererTests(unittest.TestCase):
    def test_renders_form_frame_with_full_field_set(self) -> None:
        out = _render_ext_grantee_profile(
            {
                "grantee": {
                    "msn_id": "g1",
                    "label": "Test",
                    "domains": ["example.org"],
                    "users": ["alice@example.org"],
                }
            }
        )
        self.assertEqual(out["grantee_msn_id"], "g1")
        frame = out["form_frame"]
        self.assertEqual(frame["component_type"], "form")
        field_keys = [f["key"] for f in frame["payload"]["fields"]]
        # Identity + 4 paypal + 4 aws_ses + 3 newsletter = 15 fields.
        self.assertEqual(len(field_keys), 15)
        self.assertIn("label", field_keys)
        self.assertIn("paypal.webhook_url", field_keys)
        self.assertIn("aws_ses.identity", field_keys)
        self.assertIn("newsletter.selected_sender_address", field_keys)

    def test_no_selected_grantee_returns_empty_message(self) -> None:
        out = _render_ext_grantee_profile({"grantee": {}})
        self.assertIsNone(out["form_frame"])
        self.assertIn("Select a grantee", out["empty_message"])

    def test_submit_action_routes_to_save_endpoint(self) -> None:
        out = _render_ext_grantee_profile({"grantee": {"msn_id": "g1", "label": "G"}})
        submit = out["form_frame"]["payload"]["submit_action"]
        self.assertEqual(submit["route"], "/__fnd/grantee/save")
        self.assertEqual(submit["payload"]["msn_id"], "g1")


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class GranteeProfileSaveRouteTests(unittest.TestCase):
    def _build_app(self) -> tuple:
        tmp = Path(tempfile.mkdtemp(prefix="phase9_grantee_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        grantee_dir = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.org",
            webapps_root=tmp / "webapps",
        )
        return create_app(config), grantee_dir

    def test_save_identity_field_round_trips_to_disk(self) -> None:
        app, grantee_dir = self._build_app()
        path = _seed_grantee(grantee_dir, "g1", label="Original")
        client = app.test_client()
        resp = client.post(
            "/__fnd/grantee/save",
            json={"msn_id": "g1", "fields": {"label": "Updated"}},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["profile"]["label"], "Updated")
        # Confirm the on-disk file reflects the change.
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["label"], "Updated")

    def test_save_dotted_keys_build_paypal_subconfig(self) -> None:
        app, grantee_dir = self._build_app()
        path = _seed_grantee(grantee_dir, "g2")
        client = app.test_client()
        resp = client.post(
            "/__fnd/grantee/save",
            json={
                "msn_id": "g2",
                "fields": {
                    "paypal.webhook_url": "https://example.org/hook",
                    "paypal.client_id": "CID",
                    "paypal.environment": "live",
                },
            },
        )
        self.assertEqual(resp.status_code, 200)
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["paypal"]["webhook_url"], "https://example.org/hook")
        self.assertEqual(on_disk["paypal"]["client_id"], "CID")
        self.assertEqual(on_disk["paypal"]["environment"], "live")

    def test_invalid_request_returns_400(self) -> None:
        app, _ = self._build_app()
        client = app.test_client()
        # Missing msn_id.
        resp = client.post("/__fnd/grantee/save", json={"fields": {"label": "x"}})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_request")
        # Missing fields.
        resp = client.post("/__fnd/grantee/save", json={"msn_id": "g1"})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_grantee_returns_404(self) -> None:
        app, _ = self._build_app()
        client = app.test_client()
        resp = client.post(
            "/__fnd/grantee/save",
            json={"msn_id": "does-not-exist", "fields": {"label": "x"}},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"], "grantee_not_found")

    def test_validation_failure_returns_400_with_detail(self) -> None:
        app, grantee_dir = self._build_app()
        _seed_grantee(grantee_dir, "g3")
        client = app.test_client()
        resp = client.post(
            "/__fnd/grantee/save",
            json={"msn_id": "g3", "fields": {"paypal.webhook_url": "not-a-url"}},
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertEqual(body["error"], "validation_failed")
        self.assertIn("paypal.webhook_url", body["detail"])

    def test_validation_failure_does_not_corrupt_grantee_file(self) -> None:
        app, grantee_dir = self._build_app()
        path = _seed_grantee(grantee_dir, "g4", label="Pristine")
        original = path.read_text(encoding="utf-8")
        client = app.test_client()
        # Submit a payload that mixes a valid label change with a bad URL.
        # The save must be all-or-nothing: nothing should land on disk.
        resp = client.post(
            "/__fnd/grantee/save",
            json={
                "msn_id": "g4",
                "fields": {
                    "label": "Should-not-persist",
                    "paypal.webhook_url": "not-a-url",
                },
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(path.read_text(encoding="utf-8"), original)


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class UtilitiesSurfaceListsGranteeExtensionTests(unittest.TestCase):
    def test_utilities_surface_lists_five_extensions_now(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="phase9_surface_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        response = run_portal_shell_entry(
            {
                "schema": PORTAL_SHELL_REQUEST_SCHEMA,
                "requested_surface_id": UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
            },
            portal_instance_id="fnd",
            portal_domain="example.org",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            webapps_root=tmp / "webapps",
        )
        tool_ids = [
            ext.get("tool_id")
            for ext in response.get("surface_payload", {}).get("extensions", [])
        ]
        self.assertIn("ext_grantee_profile", tool_ids)
        self.assertEqual(len(tool_ids), 5)


if __name__ == "__main__":
    unittest.main()
