"""Tests for the admin_profile_static direct-read + artifact integration.

The Garland tab's admin profile is the sandbox spatial root. For
CTS-GIS that's Ohio (`3-2-3-17`). Its identity is read directly from
the Ohio source datum at compile time and baked into the compiled
artifact's `admin_profile_static` field — bypassing the mediation /
decode pipeline that can't resolve Ohio's SAMRAS magnitude.

These tests lock the contract on two layers:

1. The pure direct-read helper `build_admin_profile_static`.
2. The `build_compiled_artifact` kwarg + artifact-field integration.
"""
from __future__ import annotations

import unittest

from MyCiteV2.packages.modules.cross_domain.cts_gis import (
    build_admin_profile_static,
    build_compiled_artifact,
)


def _ohio_like_source_datum() -> dict[str, object]:
    """A minimal source-datum payload shaped like the live Ohio file."""
    return {
        "anchor_file_version": "test",
        "reference_geojson_node_id": "3-2-3-17",
        "reference_geojson_source": "test://ohio.geojson",
        "reference_geojson": {
            "type": "FeatureCollection",
            "properties": {"exceededTransferLimit": False},
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "SHAPE__Area": 1.0,
                        "SHAPE__Length": 1.0,
                        "name": "Ohio",
                        "objectid": 1,
                        "st_abbr": "OH",
                        "st_fips": "39",
                    },
                    "geometry": {
                        "type": "MultiPolygon",
                        "coordinates": [
                            [[[-84.0, 38.0], [-80.0, 38.0], [-80.0, 42.0], [-84.0, 42.0], [-84.0, 38.0]]],
                        ],
                    },
                }
            ],
        },
        "datum_addressing_abstraction_space": {
            # The admin-root record: row carries MSN_ID + CAPITAL_MSN_ID;
            # labels[0] is "ohio". Matches the live Ohio source datum's
            # shape for `7-4-1`.
            "7-4-1": [
                ["7-4-1", "rf.3-1-2", "3-2-3-17", "rf.3-1-2",
                 "3-2-3-25-1-1-1-1", "6-0-1", "1", "6-0-2", "1"],
                ["ohio"],
            ],
            # An unrelated record — must not be picked up as the admin-root.
            "5-0-26": [
                ["5-0-26", "~", "4-2-1", "4-84-1"],
                ["23_present-district_31"],
            ],
        },
    }


class BuildAdminProfileStaticTests(unittest.TestCase):
    def test_returns_node_id_label_capital_and_fields_from_admin_root_record(self) -> None:
        admin = build_admin_profile_static(_ohio_like_source_datum())
        self.assertEqual(admin["node_id"], "3-2-3-17")
        self.assertEqual(admin["label"], "ohio")
        self.assertEqual(admin["capital_msn_id"], "3-2-3-25-1-1-1-1")
        self.assertEqual(
            admin["fields"],
            [
                {"label": "TITLE", "value": "ohio"},
                {"label": "MSN_ID", "value": "3-2-3-17"},
                {"label": "CAPITAL_MSN_ID", "value": "3-2-3-25-1-1-1-1"},
            ],
        )

    def test_geospatial_projection_uses_reference_geojson(self) -> None:
        admin = build_admin_profile_static(_ohio_like_source_datum())
        gp = admin["geospatial_projection"]
        self.assertEqual(gp["projection_state"], "projectable")
        self.assertEqual(gp["projection_source"], "reference_geojson")
        self.assertEqual(gp["feature_count"], 1)
        fc = gp["feature_collection"]
        self.assertEqual(fc["type"], "FeatureCollection")
        self.assertEqual(fc["features"][0]["geometry"]["type"], "MultiPolygon")
        self.assertEqual(gp["focus_bounds"], [-84.0, 38.0, -80.0, 42.0])

    def test_returns_inspect_only_when_no_geojson(self) -> None:
        datum = _ohio_like_source_datum()
        datum["reference_geojson"] = {"type": "FeatureCollection", "features": []}
        admin = build_admin_profile_static(datum)
        gp = admin["geospatial_projection"]
        self.assertEqual(gp["projection_state"], "inspect_only")
        self.assertEqual(gp["projection_source"], "none")
        self.assertEqual(gp["feature_count"], 0)

    def test_returns_empty_msn_when_admin_root_record_missing(self) -> None:
        datum = _ohio_like_source_datum()
        # Strip the admin-root record; the helper should fall back to
        # `reference_geojson_node_id` for the MSN_ID.
        datum["datum_addressing_abstraction_space"] = {}
        admin = build_admin_profile_static(datum)
        self.assertEqual(admin["node_id"], "3-2-3-17")  # fallback
        self.assertEqual(admin["label"], "")
        self.assertEqual(admin["capital_msn_id"], "")


class BuildCompiledArtifactAdminProfileStaticTests(unittest.TestCase):
    """`build_compiled_artifact` must accept the new `admin_profile_static`
    kwarg and emit it as a top-level field on the artifact. When omitted
    the field is absent (backwards compatible)."""

    def _minimal_inputs(self) -> dict[str, object]:
        return {
            "portal_scope_id": "fnd",
            "source_evidence": {},
            "service_surface": {},
            "navigation_canvas": {},
            "default_tool_state": {"selected_node_id": "3-2-3-17"},
            "source_layout": {
                "schema": "mycite.v2.portal.system.tools.cts_gis.source_layout.v1",
                "fingerprint": "test",
                "top_level_files": [],
                "precinct_files": [],
                "top_level_file_count": 0,
                "precinct_file_count": 0,
                "total_file_count": 0,
            },
        }

    def test_admin_profile_static_field_present_when_supplied(self) -> None:
        artifact = build_compiled_artifact(
            admin_profile_static={"node_id": "3-2-3-17", "label": "ohio"},
            **self._minimal_inputs(),
        )
        self.assertIn("admin_profile_static", artifact)
        self.assertEqual(artifact["admin_profile_static"]["node_id"], "3-2-3-17")
        self.assertEqual(artifact["admin_profile_static"]["label"], "ohio")

    def test_admin_profile_static_field_absent_when_omitted(self) -> None:
        artifact = build_compiled_artifact(**self._minimal_inputs())
        self.assertNotIn(
            "admin_profile_static",
            artifact,
            "omitting the kwarg must NOT add an empty `admin_profile_static` — keeps existing artifacts byte-identical",
        )

    def test_admin_profile_static_field_absent_when_none_or_empty(self) -> None:
        for value in (None, {}):
            with self.subTest(value=value):
                artifact = build_compiled_artifact(
                    admin_profile_static=value,
                    **self._minimal_inputs(),
                )
                self.assertNotIn("admin_profile_static", artifact)


if __name__ == "__main__":
    unittest.main()
