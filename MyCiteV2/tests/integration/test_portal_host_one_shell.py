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

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app


@unittest.skipUnless(FLASK_AVAILABLE, "flask is not installed")
class PortalHostOneShellIntegrationTests(unittest.TestCase):
    def test_host_serves_canonical_routes_and_shell_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_dir = root / "public"
            private_dir = root / "private"
            data_dir = root / "data"
            webapps_root = root / "webapps"
            for path in (public_dir, private_dir, data_dir, webapps_root):
                path.mkdir(parents=True, exist_ok=True)

            config = V2PortalHostConfig(
                portal_instance_id="fnd",
                public_dir=public_dir,
                private_dir=private_dir,
                data_dir=data_dir,
                portal_domain="fruitfulnetworkdevelopment.com",
                webapps_root=webapps_root,
            )
            app = create_app(config)
            client = app.test_client()

            self.assertEqual(client.get("/portal/system").status_code, 200)
            self.assertEqual(client.get("/portal/system/operational-status").status_code, 200)
            self.assertEqual(client.get("/portal/network").status_code, 200)
            self.assertEqual(client.get("/portal/utilities").status_code, 200)
            self.assertEqual(client.get("/portal/system/activity").status_code, 404)
            self.assertEqual(client.get("/portal/system/profile-basics").status_code, 404)

            shell_response = client.post(
                "/portal/api/v2/shell",
                json={
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.root",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                },
            )
            self.assertEqual(shell_response.status_code, 200)
            payload = shell_response.get_json()
            self.assertEqual(payload["schema"], "mycite.v2.portal.runtime.envelope.v1")
            self.assertEqual(payload["surface_id"], "system.root")
            self.assertEqual(payload["canonical_route"], "/portal/system")
            self.assertEqual(payload["canonical_query"]["file"], "anthology")

            tool_response = client.post(
                "/portal/api/v2/system/tools/aws",
                json={"schema": "mycite.v2.portal.system.tools.aws.request.v1"},
            )
            self.assertEqual(tool_response.status_code, 200)
            tool_payload = tool_response.get_json()
            self.assertEqual(tool_payload["surface_id"], "system.tools.aws")

            profile_action = client.post(
                "/portal/api/v2/system/workspace/profile-basics",
                json={
                    "schema": "mycite.v2.portal.system.workspace.profile_basics.action.request.v1",
                    "profile_title": "Example profile",
                    "profile_summary": "Workspace-owned profile summary.",
                    "contact_email": "ops@example.com",
                    "public_website_url": "https://example.com",
                },
            )
            self.assertEqual(profile_action.status_code, 200)
            profile_payload = profile_action.get_json()
            self.assertEqual(profile_payload["surface_id"], "system.root")


if __name__ == "__main__":
    unittest.main()
