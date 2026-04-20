from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "MyCiteV2" / "scripts" / "repair_cts_gis_from_reference_geojson.py"

_SPEC = importlib.util.spec_from_file_location("repair_cts_gis_from_reference_geojson", SCRIPT_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load script module from {SCRIPT_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _reference_geojson() -> dict[str, object]:
    ring = [[-81.60, 41.10], [-81.58, 41.10], [-81.58, 41.12], [-81.60, 41.12], [-81.60, 41.10]]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        ],
    }


def _bad_source_payload(node_id: str) -> dict[str, object]:
    return {
        "anchor_file_version": "<hash here>",
        "reference_geojson": _reference_geojson(),
        "reference_geojson_source": "test://reference",
        "reference_geojson_node_id": node_id,
        "datum_addressing_abstraction_space": {
            "4-4-1": [["4-4-1", "rf.3-1-1", "3-76-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0"], ["outer"]],
            "5-0-1": [["5-0-1", "~", "4-4-1"], ["shape"]],
            "7-3-1": [["7-3-1", "rf.3-1-2", node_id, "5-0-1", "1"], ["node"]],
        },
    }


def _state_like_payload(node_id: str) -> dict[str, object]:
    return {
        "anchor_file_version": "<hash here>",
        "reference_geojson": _reference_geojson(),
        "reference_geojson_source": "test://state-reference",
        "reference_geojson_node_id": node_id,
        "datum_addressing_abstraction_space": {
            "4-2-1": [["4-2-1", "rf.3-1-1", "3-76-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0-0"], ["district_ring"]],
            "4-4-1": [["4-4-1", "rf.3-1-1", "3-76-1-1-1-1-1-1-1-1-1-1-1-1-1-1-1-1"], ["state_ring"]],
            "5-0-1": [["5-0-1", "~", "4-4-1"], ["state_polygon"]],
            "5-0-26": [["5-0-26", "~", "4-2-1"], ["district_polygon"]],
            "6-0-1": [["6-0-1", "~", "5-0-1"], ["state_boundary_collection"]],
            "6-0-2": [["6-0-2", "~", "5-0-26"], ["district_set_collection"]],
            "7-4-1": [["7-4-1", "rf.3-1-2", node_id, "6-0-1", "1", "6-0-2", "1"], ["ohio"]],
        },
    }


class RepairCtsGisFromReferenceGeojsonTests(unittest.TestCase):
    def test_encode_reference_rows_is_deterministic(self) -> None:
        reference = _reference_geojson()

        first = _MODULE._encode_reference_rows(
            reference,
            used_addresses=set(),
            primary_collection_row_address="6-0-1",
        )
        second = _MODULE._encode_reference_rows(
            reference,
            used_addresses=set(),
            primary_collection_row_address="6-0-1",
        )

        self.assertEqual(first, second)
        self.assertIn("6-0-1", first)

    def test_dry_run_reports_candidate_and_writes_manifest(self) -> None:
        node_id = "3-2-3-17-77-9-11"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            source_path = (
                data_root
                / "sandbox"
                / "cts-gis"
                / "sources"
                / f"sc.3-2-3-17-77-1-6-4-1-4.fnd.{node_id}.json"
            )
            _write_json(source_path, _bad_source_payload(node_id))

            manifest_path = root / "manifest.json"
            report_json_path = root / "report.json"
            report_md_path = root / "report.md"

            old_argv = list(sys.argv)
            try:
                sys.argv = [
                    "repair_cts_gis_from_reference_geojson.py",
                    "--data-root",
                    str(data_root),
                    "--manifest-path",
                    str(manifest_path),
                    "--report-json",
                    str(report_json_path),
                    "--report-markdown",
                    str(report_md_path),
                ]
                result = _MODULE.main()
            finally:
                sys.argv = old_argv

            self.assertEqual(result, 0)
            report = json.loads(report_json_path.read_text(encoding="utf-8"))
            self.assertTrue(report["dry_run"])
            self.assertEqual(report["documents"][0]["status"], "dry_run_candidate")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["entries"][0]["node_id"], node_id)

    def test_apply_rebuilds_rows_from_reference(self) -> None:
        node_id = "3-2-3-17-77-9-12"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            source_path = (
                data_root
                / "sandbox"
                / "cts-gis"
                / "sources"
                / f"sc.3-2-3-17-77-1-6-4-1-4.fnd.{node_id}.json"
            )
            _write_json(source_path, _bad_source_payload(node_id))
            manifest_path = root / "manifest.json"
            report_json_path = root / "report.json"
            report_md_path = root / "report.md"

            old_argv = list(sys.argv)
            try:
                sys.argv = [
                    "repair_cts_gis_from_reference_geojson.py",
                    "--data-root",
                    str(data_root),
                    "--manifest-path",
                    str(manifest_path),
                    "--report-json",
                    str(report_json_path),
                    "--report-markdown",
                    str(report_md_path),
                    "--apply",
                ]
                result = _MODULE.main()
            finally:
                sys.argv = old_argv

            self.assertEqual(result, 0)
            repaired = json.loads(source_path.read_text(encoding="utf-8"))
            self.assertIn("6-0-1", repaired["datum_addressing_abstraction_space"])
            findings = _MODULE.summit_repair._reference_geometry_findings(source_path, repaired)
            self.assertEqual(findings, [])

    def test_apply_preserves_supplemental_collection_rows_for_state_like_profile(self) -> None:
        node_id = "3-2-3-17"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            source_path = (
                data_root
                / "sandbox"
                / "cts-gis"
                / "sources"
                / f"sc.3-2-3-17-77-1-6-4-1-4.fnd.{node_id}.json"
            )
            _write_json(source_path, _state_like_payload(node_id))
            manifest_path = root / "manifest.json"
            report_json_path = root / "report.json"
            report_md_path = root / "report.md"

            old_argv = list(sys.argv)
            try:
                sys.argv = [
                    "repair_cts_gis_from_reference_geojson.py",
                    "--data-root",
                    str(data_root),
                    "--manifest-path",
                    str(manifest_path),
                    "--report-json",
                    str(report_json_path),
                    "--report-markdown",
                    str(report_md_path),
                    "--node-id",
                    node_id,
                    "--apply",
                ]
                result = _MODULE.main()
            finally:
                sys.argv = old_argv

            self.assertEqual(result, 0)
            repaired = json.loads(source_path.read_text(encoding="utf-8"))
            space = repaired["datum_addressing_abstraction_space"]
            self.assertIn("6-0-2", space)
            self.assertIn("5-0-26", space)
            owner_tokens = space["7-4-1"][0]
            self.assertEqual(owner_tokens[0], "7-4-1")
            self.assertIn("6-0-1", owner_tokens)
            self.assertIn("6-0-2", owner_tokens)


if __name__ == "__main__":
    unittest.main()
