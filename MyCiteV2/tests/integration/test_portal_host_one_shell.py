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
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, build_shell_asset_manifest, create_app
    from MyCiteV2.packages.adapters.filesystem.network_root_read_model import build_system_log_document


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_network_chronology_authority(data_dir: Path) -> None:
    (data_dir / "system").mkdir(parents=True, exist_ok=True)
    _write_json(
        data_dir / "system" / "anthology.json",
        {
            "1-1-1": [
                [
                    "1-1-1",
                    "0-0-1",
                    "00000010000110000000110011010101111000011011001100011101111001111101000111110100011111010001011011010111000111100111100",
                ],
                ["HOPS-chronological"],
            ]
        },
    )
    _write_json(
        data_dir / "system" / "sources" / "sc.fnd.quadrennium_cycle.json",
        {
            "datum_addressing_abstraction_space": {
                "1-1-1": [["1-1-1", "rf.0-0-1", "00000100011100000101100100011011111101110110110101110001111001111001111101000"], ["HOPS-quadrennium_cycle"]],
                "2-0-1": [["2-0-1", "~", "1-1-1"], ["HOPS-space-quadrennium"]],
                "3-1-1": [["3-1-1", "2-0-1", "0"], ["HOPS-babelette-quadrennium_cycle"]],
            }
        },
    )


def _write_aws_csm_state(private_dir: Path) -> None:
    tool_root = private_dir / "utilities" / "tools" / "aws-csm"
    tool_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        tool_root / "spec.json",
        {
            "schema": "mycite.portal.tool_mediation.v1",
            "tool_id": "aws_csm",
            "label": "AWS-CSM",
        },
    )
    _write_json(
        tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json",
        {
            "schema": "mycite.portal.tool_collection.v1",
            "tool_id": "aws_csm",
            "member_files": [
                "spec.json",
                "aws-csm.fnd.dylan.json",
                "newsletter/newsletter.fruitfulnetworkdevelopment.com.profile.json",
            ],
        },
    )
    _write_json(
        tool_root / "aws-csm.fnd.dylan.json",
        {
            "identity": {
                "profile_id": "aws-csm.fnd.dylan",
                "domain": "fruitfulnetworkdevelopment.com",
                "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                "single_user_email": "dylan@fruitfulnetworkdevelopment.com",
                "role": "operator",
                "mailbox_local_part": "dylan",
            },
            "workflow": {"lifecycle_state": "ready", "handoff_status": "accepted"},
            "verification": {"portal_state": "verified"},
            "provider": {"aws_ses_identity_status": "verified"},
            "smtp": {"forward_to_email": "dylan@fruitfulnetworkdevelopment.com"},
            "inbound": {"receive_state": "configured", "receive_verified": "yes"},
        },
    )
    newsletter_root = tool_root / "newsletter"
    _write_json(
        newsletter_root / "newsletter.fruitfulnetworkdevelopment.com.profile.json",
        {
            "domain": "fruitfulnetworkdevelopment.com",
            "list_address": "news@fruitfulnetworkdevelopment.com",
            "sender_address": "news@fruitfulnetworkdevelopment.com",
            "selected_author_profile_id": "aws-csm.fnd.dylan",
            "selected_author_address": "dylan@fruitfulnetworkdevelopment.com",
            "delivery_mode": "manual",
            "last_dispatch_id": "dispatch-001",
        },
    )
    _write_json(
        newsletter_root / "newsletter.fruitfulnetworkdevelopment.com.contacts.json",
        {
            "contacts": [
                {"email": "reader@example.com", "subscribed": True},
                {"email": "former@example.com", "subscribed": False},
            ],
            "dispatches": [{"dispatch_id": "dispatch-001"}],
        },
    )


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
            (data_dir / "system").mkdir(parents=True, exist_ok=True)
            _write_network_chronology_authority(data_dir)
            _write_json(
                data_dir / "system" / "anthology.json",
                {
                    "1-1-1": [
                        [
                            "1-1-1",
                            "0-0-1",
                            "00000010000110000000110011010101111000011011001100011101111001111101000111110100011111010001011011010111000111100111100",
                        ],
                        ["HOPS-chronological"],
                    ],
                    "1-0-1": [["1-0-1", "~", "fruitfulnetworkdevelopment.com", "", "tenant-profile-1"], ["fruitfulnetworkdevelopment.com"]],
                },
            )
            _write_json(
                data_dir / "system" / "system_log.json",
                build_system_log_document(
                    records=[
                        {
                            "source_key": "canonical-general",
                            "source_kind": "canonical_seed",
                            "source_timestamp": "2026-07-04T00:00:00Z",
                            "title": "americas_250th_anniversary_2026_07_04",
                            "label": "americas_250th_anniversary_2026_07_04",
                            "event_type_slug": "general_event",
                            "event_type_label": "general_event",
                            "status": "scheduled",
                            "counterparty": "",
                            "contract_id": "",
                            "hops_timestamp": "0-0-0-507-916-0-0-0",
                            "raw": {"kind": "calendar"},
                        }
                    ],
                    preserved_kind_labels={"general_event": "general_event"},
                ),
            )
            _write_aws_csm_state(private_dir)
            _write_json(
                private_dir / "config.json",
                {"msn_id": "3-2-3-17-77-1-6-4-1-4", "tool_exposure": {"aws_csm": {"enabled": True}}},
            )
            (public_dir / "tenant-profile-1.json").write_text(
                '{"title":"Example Profile","summary":"Public summary"}\n',
                encoding="utf-8",
            )

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
            retired_home_route = "/portal/" + "home"
            retired_fnd_route = "/portal/" + "fnd"
            retired_tff_route = "/portal/" + "tff"

            root_response = client.get("/portal", follow_redirects=False)
            self.assertEqual(root_response.status_code, 302)
            self.assertEqual(root_response.headers["Location"], "/portal/system")
            system_response = client.get("/portal/system")
            self.assertEqual(system_response.status_code, 200)
            self.assertEqual(client.get("/portal/network").status_code, 200)
            self.assertEqual(client.get("/portal/utilities").status_code, 200)
            self.assertEqual(client.get("/portal/system/tools/aws-csm").status_code, 200)
            self.assertEqual(client.get("/portal/system/tools/cts-gis").status_code, 200)
            self.assertEqual(client.get("/portal/system/tools/aws", follow_redirects=False).status_code, 302)
            self.assertEqual(
                client.get("/portal/system/tools/aws", follow_redirects=False).headers["Location"],
                "/portal/system/tools/aws-csm",
            )
            self.assertEqual(client.get(retired_home_route).status_code, 404)
            self.assertEqual(client.get(retired_fnd_route).status_code, 404)
            self.assertEqual(client.get(retired_tff_route).status_code, 404)
            self.assertEqual(client.get("/portal/system/activity").status_code, 404)
            self.assertEqual(client.get("/portal/system/profile-basics").status_code, 404)
            health_response = client.get("/portal/healthz")
            self.assertEqual(health_response.status_code, 200)
            health_payload = health_response.get_json()
            self.assertTrue(all(health_payload["static_files_present"].values()))
            self.assertEqual(health_payload["shell_asset_manifest"], build_shell_asset_manifest())
            self.assertIn(
                "v2_portal_tool_surface_adapter.js",
                [entry["file"] for entry in health_payload["shell_asset_manifest"]["scripts"]["shell_modules"]],
            )

            system_html = system_response.get_data(as_text=True)
            self.assertEqual(system_html.count("data-theme-selector"), 1)
            self.assertNotIn("pagehead--withTools", system_html)
            self.assertIn("Toggle Control Panel", system_html)
            self.assertIn("Toggle Workbench", system_html)
            self.assertIn("Toggle Interface Panel", system_html)
            self.assertNotIn(">Control Panel</button>", system_html)
            self.assertNotIn(">Workbench</button>", system_html)
            self.assertIn('data-tool-panel-lock="false"', system_html)
            self.assertIn('data-shell-lockable="tool-panel"', system_html)
            self.assertIn('data-workbench-collapsed="false"', system_html)
            self.assertIn('id="v2-shell-asset-manifest"', system_html)
            for asset in (
                [health_payload["shell_asset_manifest"]["styles"]["portal_css"]]
                + [
                    health_payload["shell_asset_manifest"]["scripts"]["portal_js"],
                    health_payload["shell_asset_manifest"]["scripts"]["shell_entry"],
                ]
                + health_payload["shell_asset_manifest"]["scripts"]["shell_modules"]
            ):
                self.assertIn(asset["url"], system_html)

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
            self.assertEqual(payload["shell_composition"]["regions"]["control_panel"]["kind"], "focus_selection_panel")
            self.assertTrue(payload["shell_composition"]["inspector_collapsed"])
            self.assertTrue(payload["shell_composition"]["interface_panel_collapsed"])
            self.assertFalse(payload["shell_composition"]["workbench_collapsed"])
            self.assertEqual(
                payload["shell_composition"]["regions"]["interface_panel"],
                payload["shell_composition"]["regions"]["inspector"],
            )
            activity_items = payload["shell_composition"]["regions"]["activity_bar"]["items"]
            self.assertNotIn("system.root", [item["item_id"] for item in activity_items])
            aws_items = [item for item in activity_items if item["item_id"] == "system.tools.aws_csm"]
            self.assertEqual(len(aws_items), 1)
            self.assertEqual(aws_items[0]["label"], "AWS-CSM")
            self.assertEqual(aws_items[0]["href"], "/portal/system/tools/aws-csm")
            operational_payload = client.post(
                "/portal/api/v2/shell",
                json={
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.legacy_removed_surface",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                },
            ).get_json()
            self.assertEqual(operational_payload["surface_id"], "system.root")
            self.assertEqual(operational_payload["error"]["code"], "surface_unknown")
            network_payload = client.post(
                "/portal/api/v2/shell",
                json={
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "network.root",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                    "surface_query": {"view": "system_logs"},
                },
            ).get_json()
            self.assertEqual(network_payload["surface_id"], "network.root")
            self.assertFalse(network_payload["reducer_owned"])
            self.assertEqual(network_payload["canonical_query"], {"view": "system_logs"})
            self.assertEqual(network_payload["surface_payload"]["kind"], "network_system_log_workspace")
            self.assertEqual(network_payload["shell_composition"]["regions"]["control_panel"]["kind"], "focus_selection_panel")
            self.assertTrue(network_payload["shell_composition"]["inspector_collapsed"])
            self.assertTrue(network_payload["shell_composition"]["interface_panel_collapsed"])
            self.assertFalse(network_payload["shell_composition"]["workbench_collapsed"])

            aws_shell_payload = client.post(
                "/portal/api/v2/shell",
                json={
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.tools.aws_csm",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                },
            ).get_json()
            self.assertEqual(aws_shell_payload["surface_id"], "system.tools.aws_csm")
            self.assertFalse(aws_shell_payload["reducer_owned"])
            self.assertEqual(aws_shell_payload["canonical_query"], {"view": "domains"})
            self.assertEqual(aws_shell_payload["shell_composition"]["regions"]["workbench"]["kind"], "aws_csm_workbench")
            self.assertEqual(
                aws_shell_payload["shell_composition"]["regions"]["control_panel"]["context_items"],
                [
                    {"label": "Sandbox", "value": "AWS-CSM"},
                    {"label": "File", "value": "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json"},
                    {"label": "Mediation", "value": "spec.json"},
                ],
            )
            self.assertTrue(aws_shell_payload["shell_composition"]["workbench_collapsed"])
            self.assertFalse(aws_shell_payload["shell_composition"]["interface_panel_collapsed"])
            self.assertEqual(
                aws_shell_payload["shell_composition"]["regions"]["interface_panel"],
                aws_shell_payload["shell_composition"]["regions"]["inspector"],
            )

            tool_response = client.post(
                "/portal/api/v2/system/tools/aws-csm",
                json={"schema": "mycite.v2.portal.system.tools.aws_csm.request.v1"},
            )
            self.assertEqual(tool_response.status_code, 200)
            tool_payload = tool_response.get_json()
            self.assertEqual(tool_payload["surface_id"], "system.tools.aws_csm")
            self.assertEqual(tool_payload["canonical_query"], {"view": "domains"})
            self.assertEqual(tool_payload["surface_payload"]["kind"], "aws_csm_workspace")

            cts_gis_ok = client.post(
                "/portal/api/v2/system/tools/cts-gis",
                json={"schema": "mycite.v2.portal.system.tools.cts_gis.request.v1"},
            )
            self.assertEqual(cts_gis_ok.status_code, 200)
            self.assertEqual(cts_gis_ok.get_json()["surface_id"], "system.tools.cts_gis")

            cts_gis_legacy = client.post(
                "/portal/api/v2/system/tools/cts-gis",
                json={
                    "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
                    "selected_document_id": "sandbox:" + ("map" + "s") + ":sc.legacy.json",
                },
            )
            self.assertEqual(cts_gis_legacy.status_code, 400)
            legacy_error = cts_gis_legacy.get_json()
            self.assertEqual(legacy_error["error"]["code"], "legacy_maps_alias_unsupported")

            profile_action = client.post(
                "/portal/api/v2/system/workspace/profile-basics",
                json={
                    "schema": "mycite.v2.portal.system.workspace.profile_basics.action.request.v1",
                    "profile_title": "Example Profile",
                    "profile_summary": "Workspace-owned profile summary.",
                    "contact_email": "ops@example.com",
                    "public_website_url": "https://example.com",
                },
            )
            self.assertEqual(profile_action.status_code, 200)
            profile_payload = profile_action.get_json()
            self.assertEqual(profile_payload["surface_id"], "system.root")

    def test_client_boot_prefers_server_shell_posture_on_first_v2_hydration(self) -> None:
        portal_js = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "portal.js"
        ).read_text(encoding="utf-8")
        shell_core = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_shell_core.js"
        ).read_text(encoding="utf-8")

        self.assertIn("firstV2ShellCompositionApplied", portal_js)
        self.assertIn("applyShellPostureFromDom({ useStoredWorkbenchPreference: false })", portal_js)
        self.assertIn("fromShellComposition: true", shell_core)


if __name__ == "__main__":
    unittest.main()
