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


def _cts_gis_regions(request_payload: dict) -> dict:
    data_dir, private_dir = _preferred_fnd_paths()
    envelope = run_portal_cts_gis(
        request_payload,
        data_dir=str(data_dir),
        private_dir=str(private_dir),
        tool_exposure_policy=None,
        portal_instance_id="fnd",
        portal_domain="fruitfulnetworkdevelopment.com",
    )
    return dict(envelope["shell_composition"]["regions"])  # type: ignore[index]


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
        self.assertEqual(interface_body.get("default_tab_id"), "garland")
        self.assertEqual(
            [tab.get("id") for tab in list(interface_body.get("tabs") or [])],
            ["garland", "diktataograph"],
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

    def test_garland_emits_modular_component_shells_and_context_controls(self) -> None:
        regions = _cts_gis_regions(
            {
                "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                "runtime_mode": "production_strict",
                "tool_state": {
                    "active_path": ["3", "3-2", "3-2-3", "3-2-3-17"],
                    "selected_node_id": "3-2-3-17",
                    "aitas": {
                        "attention_node_id": "3-2-3-17",
                        "intention_rule_id": "self",
                        "time_directive": "current",
                    },
                },
            }
        )
        interface_body = dict(regions["interface_panel"]["interface_body"])
        frames = list(interface_body.get("component_frames") or [])
        self.assertEqual(interface_body.get("layout"), "garland_tabbed")
        self.assertEqual(interface_body.get("narrow_layout"), "garland_tabbed")
        self.assertNotEqual(interface_body.get("layout"), "diktataograph_garland_split")
        self.assertTrue(frames)
        garland_group = frames[0]
        self.assertEqual(garland_group.get("component_type"), "component_group")
        self.assertEqual(garland_group.get("tab_id"), "garland")
        self.assertFalse(garland_group.get("frozen"))
        children = list((garland_group.get("payload") or {}).get("children") or [])
        child_ids = {child.get("frame_id") for child in children}
        self.assertEqual(
            child_ids,
            {
                "administrative_node_profile",
                "administrative_log_entry_listing",
                "precinct_profile",
                "log_listing_other_voters",
                "election_history",
                "voter_profile",
            },
        )
        self.assertEqual(
            {child.get("component_type") for child in children},
            {"profile", "listing", "chronology_matrix"},
        )
        for child in children:
            initializer = dict(child.get("initializer") or {})
            self.assertEqual(initializer.get("verb"), "mediate")
            self.assertEqual(initializer.get("target_authority"), "cts_gis")

        controls = list((regions["control_panel"].get("nimm_aitas_control") or {}).get("context_controls") or [])
        self.assertEqual(
            [control.get("context_id") for control in controls],
            ["attention", "intention", "time", "archetype", "spatial"],
        )
        self.assertEqual([control.get("control_type") for control in controls], ["select", "stepper", "directional", "select", "directional"])

    def test_control_panel_excludes_legacy_directive_sections(self) -> None:
        regions = _cts_gis_regions(
            {
                "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                "runtime_mode": "production_strict",
                "tool_state": {
                    "active_path": ["3", "3-2", "3-2-3", "3-2-3-17"],
                    "selected_node_id": "3-2-3-17",
                    "aitas": {
                        "attention_node_id": "3-2-3-17",
                        "intention_rule_id": "self",
                        "time_directive": "current",
                    },
                },
            }
        )
        control_panel = regions["control_panel"]

        navigation_titles = {
            (group.get("title") or "")
            for group in (control_panel.get("navigation_groups") or [])
        }
        self.assertNotIn(
            "STATE DIRECTIVE",
            navigation_titles,
            "STATE DIRECTIVE has been replaced by the AITAS context-control table",
        )
        for title in navigation_titles:
            self.assertFalse(
                title.startswith("Sandbox:"),
                f"unexpected sandbox navigation group {title!r} should be filtered out for CTS-GIS",
            )

        tool_extensions = dict(control_panel.get("tool_extensions") or {})
        for obsolete_key in (
            "cts_gis_attention",
            "cts_gis_intention",
            "cts_gis_time",
            "cts_gis_archetype",
        ):
            self.assertNotIn(
                obsolete_key,
                tool_extensions,
                f"{obsolete_key} duplicates the AITAS context-control table",
            )

        condition_labels = {
            (row.get("label") or "")
            for row in (control_panel.get("context_conditions") or [])
        }
        self.assertNotIn(
            "Sandbox",
            condition_labels,
            "Sandbox row duplicates the surface label already shown in the panel header",
        )
        self.assertIn(
            "File",
            condition_labels,
            "File row is still required to identify the active anchor file",
        )

    def test_empty_request_defaults_attention_to_presumed_ohio_root(self) -> None:
        """When the Garland tab loads with no explicit selection (no
        active_path, selected_node_id, or attention_node_id in the request
        body), the daemon-load contract requires the presumed attention to
        be the Ohio root administrative node "3-2-3-17", reached by
        mediating "1-1-2" through the CTS-GIS spatial context. The
        wireframe must mediate, navigate, and project at the presumed
        default — not at whatever leaf node the compiled artifact landed on."""
        from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
            CTS_GIS_PRESUMED_ATTENTION_NODE_ID,
        )

        regions = _cts_gis_regions(
            {
                "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                "runtime_mode": "production_strict",
                # Empty tool_state — no selection on the wire.
                "tool_state": {},
            }
        )
        self.assertEqual(CTS_GIS_PRESUMED_ATTENTION_NODE_ID, "3-2-3-17")

        interface_body = dict(regions["interface_panel"]["interface_body"])
        navigation = dict(interface_body.get("navigation_canvas") or {})
        self.assertEqual(
            navigation.get("active_node_id"),
            CTS_GIS_PRESUMED_ATTENTION_NODE_ID,
            f"navigation_canvas active_node_id should be {CTS_GIS_PRESUMED_ATTENTION_NODE_ID!r} when the request carries no explicit selection",
        )

        frames = list(interface_body.get("component_frames") or [])
        self.assertTrue(frames)
        children = list((frames[0].get("payload") or {}).get("children") or [])
        admin_profile = next(
            (child for child in children if child.get("frame_id") == "administrative_node_profile"),
            None,
        )
        self.assertIsNotNone(admin_profile)
        admin_payload = dict(admin_profile.get("payload") or {})
        self.assertEqual(
            admin_payload.get("msn_id"),
            CTS_GIS_PRESUMED_ATTENTION_NODE_ID,
            "admin profile must mediate on the presumed Ohio root when no explicit selection is provided",
        )

    def test_administrative_node_profile_emits_bare_minimum_filament_fields(self) -> None:
        """The admin_node profile should only carry the three SAMRAS filament
        values that a NIMM mediation directive can resolve from the source
        datum (TITLE / MSN_ID / CAPITAL_MSN_ID), plus the DISTRICT_COLLECTIONS
        collection. Computed display values (FEATURE_COUNT / CHILD_COUNT and
        the collection-count field-row) must NOT appear, so the wireframe
        never claims data that did not come out of mediation."""
        regions = _cts_gis_regions(
            {
                "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                "runtime_mode": "production_strict",
                "tool_state": {
                    "active_path": ["3", "3-2", "3-2-3", "3-2-3-17"],
                    "selected_node_id": "3-2-3-17",
                    "aitas": {
                        "attention_node_id": "3-2-3-17",
                        "intention_rule_id": "self",
                        "time_directive": "current",
                    },
                },
            }
        )
        interface_body = dict(regions["interface_panel"]["interface_body"])
        frames = list(interface_body.get("component_frames") or [])
        self.assertTrue(frames)
        children = list((frames[0].get("payload") or {}).get("children") or [])
        admin_profile = next(
            (child for child in children if child.get("frame_id") == "administrative_node_profile"),
            None,
        )
        self.assertIsNotNone(admin_profile, "administrative_node_profile must be present in the Garland group")
        admin_fields = list((admin_profile.get("payload") or {}).get("fields") or [])
        field_labels = [f.get("label") for f in admin_fields]
        self.assertEqual(
            field_labels,
            ["TITLE", "MSN_ID", "CAPITAL_MSN_ID"],
            "admin_node profile must carry only the three SAMRAS filament fields the source datum can resolve",
        )
        for forbidden in ("FEATURE_COUNT", "CHILD_COUNT", "DISTRICT_COLLECTIONS", "STATE"):
            self.assertNotIn(
                forbidden,
                field_labels,
                f"{forbidden!r} is a computed display value, not source filament data — it must not appear in the admin profile",
            )

    def test_garland_emits_wireframe_placeholder_counts(self) -> None:
        regions = _cts_gis_regions(
            {
                "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                "runtime_mode": "production_strict",
                "tool_state": {
                    "active_path": ["3", "3-2", "3-2-3", "3-2-3-17"],
                    "selected_node_id": "3-2-3-17",
                    "aitas": {
                        "attention_node_id": "3-2-3-17",
                        "intention_rule_id": "self",
                        "time_directive": "current",
                    },
                },
            }
        )
        interface_body = dict(regions["interface_panel"]["interface_body"])
        frames = list(interface_body.get("component_frames") or [])
        self.assertTrue(frames)
        children = list((frames[0].get("payload") or {}).get("children") or [])
        children_by_id = {child.get("frame_id"): child for child in children}

        admin_log_payload = (children_by_id.get("administrative_log_entry_listing") or {}).get("payload") or {}
        admin_log_rows = list(admin_log_payload.get("rows") or [])
        admin_log_placeholder = int(admin_log_payload.get("placeholder_row_count") or 0)
        # Listing contract: real rows OR placeholder rows, never both. When
        # the profile resolves district collections from the source datum,
        # those rows populate the listing; otherwise the listing paints
        # the 16-row wireframe scaffold from the mockup.
        self.assertTrue(
            (admin_log_rows and admin_log_placeholder == 0)
            or (not admin_log_rows and admin_log_placeholder == 16),
            f"admin_log must paint either real district rows or 16 placeholders, "
            f"got rows={len(admin_log_rows)} placeholder_row_count={admin_log_placeholder}",
        )

        other_voters_payload = (children_by_id.get("log_listing_other_voters") or {}).get("payload") or {}
        other_voters_rows = list(other_voters_payload.get("rows") or [])
        other_voters_placeholder = int(other_voters_payload.get("placeholder_row_count") or 0)
        self.assertTrue(
            (other_voters_rows and other_voters_placeholder == 0)
            or (not other_voters_rows and other_voters_placeholder == 16),
            f"other_voters must paint either real rows or 16 placeholders, "
            f"got rows={len(other_voters_rows)} placeholder_row_count={other_voters_placeholder}",
        )

        admin_profile = children_by_id.get("administrative_node_profile") or {}
        admin_collections = list((admin_profile.get("payload") or {}).get("collections") or [])
        self.assertTrue(admin_collections, "administrative_node_profile must carry at least one collection")
        self.assertEqual(
            int(admin_collections[0].get("placeholder_item_count") or 0),
            3,
            "DISTRICT_COLLECTIONS must emit 3 wireframe placeholder items",
        )

        precinct_profile = children_by_id.get("precinct_profile") or {}
        precinct_collections = list((precinct_profile.get("payload") or {}).get("collections") or [])
        self.assertTrue(precinct_collections, "precinct_profile must carry at least one collection")
        self.assertEqual(
            int(precinct_collections[0].get("placeholder_item_count") or 0),
            3,
            "PRECINCT_COLLECTIONS must emit 3 wireframe placeholder items",
        )


if __name__ == "__main__":
    unittest.main()
