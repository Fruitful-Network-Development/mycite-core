from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import _normalize_request, run_portal_cts_gis
from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry


def _preferred_fnd_paths() -> tuple[Path, Path]:
    candidates = [
        Path("/srv/mycite-state/instances/fnd"),
        REPO_ROOT / "deployed" / "fnd",
    ]
    for root in candidates:
        data_dir = root / "data"
        private_dir = root / "private"
        if data_dir.exists():
            return data_dir, private_dir
    return candidates[0] / "data", candidates[0] / "private"


def _cts_gis_interface_body(request_payload: dict) -> dict:
    data_dir, private_dir = _preferred_fnd_paths()
    envelope = run_portal_cts_gis(
        request_payload,
        data_dir=str(data_dir),
        private_dir=str(private_dir),
        tool_exposure_policy=None,
        portal_instance_id="fnd",
        portal_domain="fruitfulnetworkdevelopment.com",
    )
    return dict(
        envelope["shell_composition"]["regions"]["interface_panel"]["interface_body"]  # type: ignore[index]
    )


def _without_phase_timings(value):
    if isinstance(value, dict):
        return {
            key: _without_phase_timings(item)
            for key, item in value.items()
            if key != "phase_timings_ms"
        }
    if isinstance(value, list):
        return [_without_phase_timings(item) for item in value]
    return value


class PortalCtsGisRuntimeTests(unittest.TestCase):
    def test_direct_cts_gis_endpoint_matches_shell_runtime_envelope(self) -> None:
        request_payload = {
            "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
            "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
            "mediation_state": {
                "attention_node_id": "3-2-3-17-77",
                "intention_token": "descendants_depth_1_or_2",
            },
        }
        portal_scope, shell_state, normalized_payload, _ = _normalize_request(request_payload)
        shell_request = dict(normalized_payload)
        shell_request["schema"] = "mycite.v2.portal.shell.request.v1"
        shell_request["requested_surface_id"] = "system.tools.cts_gis"
        shell_request["portal_scope"] = portal_scope.to_dict()
        shell_request["shell_state"] = shell_state.to_dict()
        shell_request.pop("surface_query", None)

        direct_envelope = run_portal_cts_gis(
            request_payload,
            data_dir=None,
            private_dir=None,
            tool_exposure_policy=None,
            portal_instance_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
        )
        shell_envelope = run_portal_shell_entry(
            shell_request,
            portal_instance_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
            data_dir=None,
            public_dir=None,
            private_dir=None,
            audit_storage_file=None,
            webapps_root=None,
            tool_exposure_policy=None,
        )
        direct_normalized = _without_phase_timings(direct_envelope)
        shell_normalized = _without_phase_timings(shell_envelope)
        # Shell-level route handling may carry a different top-level posture token
        # while preserving equivalent CTS-GIS payload/runtime content.
        direct_normalized.pop("read_write_posture", None)
        shell_normalized.pop("read_write_posture", None)
        self.assertEqual(direct_normalized, shell_normalized)

    def test_compiled_navigation_honors_requested_ohio_active_path(self) -> None:
        request_payload = {
            "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
            "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
            "runtime_mode": "production_strict",
            "tool_state": {
                "active_path": ["3", "3-2", "3-2-3", "3-2-3-17"],
                "selected_node_id": "3-2-3-17",
                "aitas": {"attention_node_id": "3-2-3-17", "intention_rule_id": "self"},
            },
        }
        interface_body = _cts_gis_interface_body(request_payload)
        navigation = dict(interface_body.get("navigation_canvas") or {})
        garland = dict(interface_body.get("garland_split_projection") or {})
        profile_projection = dict(garland.get("profile_projection") or {})
        active_profile = dict(profile_projection.get("active_profile") or {})

        self.assertEqual(interface_body.get("tab_host"), "shared_interface_tabs")
        self.assertEqual(interface_body.get("default_tab_id"), "diktataograph")
        self.assertEqual(
            [tab.get("id") for tab in list(interface_body.get("tabs") or [])],
            ["diktataograph", "garland"],
        )
        self.assertEqual(navigation.get("decode_state"), "ready")
        self.assertEqual(navigation.get("active_node_id"), "3-2-3-17")
        self.assertEqual(
            [entry.get("node_id") for entry in list(navigation.get("active_path") or [])],
            ["3", "3-2", "3-2-3", "3-2-3-17"],
        )
        self.assertEqual(active_profile.get("node_id"), "3-2-3-17")
        self.assertEqual(profile_projection.get("has_profile_state"), True)

    def test_compiled_navigation_reports_invalid_active_path_diagnostic(self) -> None:
        request_payload = {
            "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
            "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
            "runtime_mode": "production_strict",
            "tool_state": {
                "active_path": ["3", "3-2", "9-9-9"],
                "selected_node_id": "9-9-9",
                "aitas": {"attention_node_id": "9-9-9", "intention_rule_id": "self"},
            },
        }
        interface_body = _cts_gis_interface_body(request_payload)
        navigation = dict(interface_body.get("navigation_canvas") or {})
        diagnostics = list(navigation.get("diagnostics") or [])
        diagnostic_codes = {item.get("code") for item in diagnostics if isinstance(item, dict)}

        self.assertIn("invalid_active_path", diagnostic_codes)
        self.assertIn("unresolved_node_binding", diagnostic_codes)


if __name__ == "__main__":
    unittest.main()
