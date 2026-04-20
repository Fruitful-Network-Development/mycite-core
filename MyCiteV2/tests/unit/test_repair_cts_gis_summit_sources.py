from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "MyCiteV2" / "scripts" / "repair_cts_gis_summit_sources.py"

_SPEC = importlib.util.spec_from_file_location("repair_cts_gis_summit_sources", SCRIPT_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load script module from {SCRIPT_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def _closed_ring(points: list[list[float]]) -> list[list[float]]:
    return [*points, list(points[0])]


def _ring_row(row_address: str, points: list[list[float]], label: str = "ring") -> list[object]:
    tokens = [row_address]
    for longitude, latitude in points:
        tokens.extend(["rf.3-1-1", _MODULE._encode_hops_coordinate(longitude, latitude)])
    return [tokens, [label]]


def _reference_geojson(polygons: list[list[list[list[float]]]]) -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [
                        [[_closed_ring(ring) for ring in polygon][index] for index, ring in enumerate(polygon)]
                        for polygon in polygons
                    ],
                },
                "properties": {},
            }
        ],
    }


def _write_root_document(data_root: Path, *, suffix: str, payload: dict[str, object]) -> Path:
    source_dir = data_root / "sandbox" / "cts-gis" / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    anchor_path = data_root / "sandbox" / "cts-gis" / _MODULE.ANCHOR_NAME
    anchor_path.parent.mkdir(parents=True, exist_ok=True)
    anchor_path.write_text(json.dumps({"datum_addressing_abstraction_space": {}}, indent=2) + "\n", encoding="utf-8")
    source_path = source_dir / f"sc.3-2-3-17-77-1-6-4-1-4.fnd.{suffix}.json"
    source_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return source_path


def _matching_payload(
    *,
    suffix: str,
    polygon_row_labels: list[str] | None = None,
    reference_geojson_source: str = "docs/reference.geojson",
) -> dict[str, object]:
    outer = [[-81.60, 41.10], [-81.58, 41.10], [-81.58, 41.12], [-81.60, 41.12]]
    inner = [[-81.595, 41.105], [-81.585, 41.105], [-81.590, 41.115]]
    polygon_row_labels = list(polygon_row_labels or ["sample_boundary"])
    return {
        "anchor_file_version": "<hash here>",
        "reference_geojson": _reference_geojson([[outer, inner]]),
        "reference_geojson_source": reference_geojson_source,
        "reference_geojson_node_id": suffix,
        "datum_addressing_abstraction_space": {
            "4-4-1": _ring_row("4-4-1", outer, "outer"),
            "4-3-1": _ring_row("4-3-1", inner, "inner"),
            "5-0-1": [["5-0-1", "~", "4-4-1", "4-3-1"], polygon_row_labels],
            "7-3-1": [["7-3-1", "rf.3-1-2", suffix, "5-0-1", "1"], ["sample_node"]],
        },
    }


class RepairCtsGisSummitSourcesTests(unittest.TestCase):
    def test_reference_geometry_findings_detect_ring_ordering(self) -> None:
        suffix = "3-2-3-17-77-9-9"
        payload = _matching_payload(suffix=suffix)
        payload["datum_addressing_abstraction_space"]["5-0-1"] = [["5-0-1", "~", "4-3-1", "4-4-1"], ["sample_boundary"]]
        path = Path(f"/tmp/sc.3-2-3-17-77-1-6-4-1-4.fnd.{suffix}.json")

        findings = _MODULE._reference_geometry_findings(path, payload)

        self.assertEqual([finding["issue_type"] for finding in findings], ["ring_ordering"])
        self.assertEqual(findings[0]["rows_involved"], ["5-0-1", "4-3-1", "4-4-1"])

    def test_reference_geometry_findings_detect_polygon_and_ring_count_mismatches(self) -> None:
        suffix = "3-2-3-17-77-9-8"
        payload = _matching_payload(suffix=suffix)
        payload["reference_geojson"] = _reference_geojson(
            [
                [
                    [[-81.60, 41.10], [-81.58, 41.10], [-81.58, 41.12], [-81.60, 41.12]],
                    [[-81.595, 41.105], [-81.585, 41.105], [-81.590, 41.115]],
                ],
                [
                    [[-81.57, 41.11], [-81.56, 41.11], [-81.56, 41.12], [-81.57, 41.12]],
                ],
            ]
        )
        path = Path(f"/tmp/sc.3-2-3-17-77-1-6-4-1-4.fnd.{suffix}.json")

        findings = _MODULE._reference_geometry_findings(path, payload)

        self.assertIn("polygon_count_mismatch", [finding["issue_type"] for finding in findings])

        payload = _matching_payload(suffix=suffix)
        payload["datum_addressing_abstraction_space"]["5-0-1"] = [["5-0-1", "~", "4-4-1"], ["sample_boundary"]]
        findings = _MODULE._reference_geometry_findings(path, payload)
        self.assertIn("ring_count_mismatch", [finding["issue_type"] for finding in findings])

    def test_deterministic_findings_capture_stale_four_row_reference(self) -> None:
        findings = _MODULE._deterministic_findings(
            ["5-0-1 missing row reference 4-1505-2 aligned to 4-1505-1"],
            reference_geojson_source="docs/barberton.geojson",
        )

        self.assertEqual(findings[0]["issue_type"], "row_address_defect")
        self.assertEqual(findings[0]["rows_involved"], ["5-0-1", "4-1505-2", "4-1505-1"])
        self.assertEqual(findings[0]["recommended_action"], "needs_deterministic_repair")

    def test_audit_blocks_safe_to_strip_when_projection_with_reference_warns(self) -> None:
        suffix = "3-2-3-17-77-9-7"
        with tempfile.TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir) / "data"
            _write_root_document(data_root, suffix=suffix, payload=_matching_payload(suffix=suffix))

            def _fake_snapshot(*, drop_reference_metadata: bool, **_: object) -> dict[str, object]:
                return {
                    "projection_state": "projectable",
                    "projection_source": "hops",
                    "feature_count": 1,
                    "reference_binding_count": 7,
                    "decoded_coordinate_count": 7,
                    "failed_token_count": 0,
                    "warnings": ["reference mismatch"] if not drop_reference_metadata else [],
                }

            with mock.patch.object(_MODULE, "_projection_snapshot", side_effect=_fake_snapshot):
                report = _MODULE._audit_and_repair_data_root(
                    data_root=data_root,
                    apply_deterministic_fixes=False,
                    strip_stage_a=False,
                )

        self.assertEqual(report["document_count"], 1)
        self.assertFalse(report["documents"][0]["safe_to_strip"])
        self.assertEqual(report["documents"][0]["reference_warning_count"], 1)

    def test_build_review_report_flags_repo_state_desync_after_stripping_reference_metadata(self) -> None:
        suffix = "3-2-3-17-77-9-6"
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            state_root = Path(temp_dir) / "state"
            repo_payload = _matching_payload(suffix=suffix, polygon_row_labels=["repo_boundary"])
            state_payload = _matching_payload(suffix=suffix, polygon_row_labels=["state_boundary"])
            for key in _MODULE.REFERENCE_KEYS:
                repo_payload.pop(key, None)

            _write_root_document(repo_root, suffix=suffix, payload=repo_payload)
            _write_root_document(state_root, suffix=suffix, payload=state_payload)

            def _fake_snapshot(*, drop_reference_metadata: bool, **_: object) -> dict[str, object]:
                return {
                    "projection_state": "projectable",
                    "projection_source": "hops",
                    "feature_count": 1,
                    "reference_binding_count": 7,
                    "decoded_coordinate_count": 7,
                    "failed_token_count": 0,
                    "warnings": [],
                }

            with mock.patch.object(_MODULE, "_projection_snapshot", side_effect=_fake_snapshot):
                repo_report = _MODULE._audit_and_repair_data_root(
                    data_root=repo_root,
                    apply_deterministic_fixes=False,
                    strip_stage_a=False,
                )
                state_report = _MODULE._audit_and_repair_data_root(
                    data_root=state_root,
                    apply_deterministic_fixes=False,
                    strip_stage_a=False,
                )

            review_report = _MODULE._build_review_report([repo_report, state_report])

        self.assertEqual(review_report["document_count"], 1)
        document = review_report["documents"][0]
        self.assertEqual(document["classification"], "repo_state_drift_only")
        self.assertEqual(document["review_bucket"], "flagged")
        self.assertIn("repo_state_desync", document["finding_types"])
        self.assertEqual(document["findings"][0]["rows_involved"], ["5-0-1"])


if __name__ == "__main__":
    unittest.main()
