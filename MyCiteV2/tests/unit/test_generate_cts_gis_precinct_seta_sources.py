from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "MyCiteV2" / "scripts" / "generate_cts_gis_precinct_seta_sources.py"
SETA_INPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "personal_notes"
    / "CTS-GIS-prototype-mockup"
    / "precincts"
    / "247-17-77-0"
)

_SPEC = importlib.util.spec_from_file_location("generate_cts_gis_precinct_seta_sources", SCRIPT_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load script module from {SCRIPT_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


class GenerateCtsGisPrecinctSetaSourcesTests(unittest.TestCase):
    def test_encode_hops_coordinate_matches_known_county_reference_point(self) -> None:
        token = _MODULE.encode_hops_coordinate(-82.67339240336636, 41.4549988713787)

        self.assertEqual(
            token,
            "3-76-27-73-3-3-51-5-68-54-77-92-68-85-42-43-67-71",
        )

    def test_encode_precinct_name_bits_matches_sample_pattern(self) -> None:
        bits = _MODULE.encode_precinct_name_bits("AK01-A")

        self.assertEqual(
            bits,
            "010000010100101100110000001100010010110101000001"
            "000000000000000000000000000000000000000000000000"
            "00000000000000000000000000000000",
        )
        self.assertEqual(len(bits), 128)

    def test_builds_precinct_one_payload_with_hops_and_precinct_binding(self) -> None:
        feature = _MODULE._load_single_feature(SETA_INPUT_DIR / "setA__PRECINCT-001.geojson")
        payload = _MODULE.build_precinct_payload(feature, ruiqi_id="247-17-77-1")
        datum_space = payload["datum_addressing_abstraction_space"]

        self.assertEqual(payload["anchor_file_version"], "<hash here>")
        self.assertIn("4-129-1", datum_space)
        row4 = datum_space["4-129-1"][0]
        self.assertEqual(row4[0], "4-129-1")
        self.assertEqual(row4[1], "rf.3-1-1")
        self.assertTrue(row4[2].startswith("3-76-"))
        self.assertNotIn("-81.508581,41.163443", row4)

        row7 = datum_space["7-3-1"][0]
        self.assertEqual(
            row7,
            [
                "7-3-1",
                "rf.3-1-4",
                "247-17-77-1",
                "rf.3-1-5",
                "010000010100101100110000001100010010110101000001"
                "000000000000000000000000000000000000000000000000"
                "00000000000000000000000000000000",
                "6-0-1",
                "1",
            ],
        )
        self.assertEqual(datum_space["7-3-1"][1], ["precinct_247_17_77_1"])

    def test_multipolygon_precinct_creates_multiple_polygon_rows(self) -> None:
        feature = _MODULE._load_single_feature(SETA_INPUT_DIR / "setA__PRECINCT-003.geojson")
        payload = _MODULE.build_precinct_payload(feature, ruiqi_id="247-17-77-3")
        datum_space = payload["datum_addressing_abstraction_space"]

        polygon_rows = sorted(address for address in datum_space if address.startswith("5-0-"))
        self.assertGreater(len(polygon_rows), 1)
        self.assertEqual(datum_space["6-0-1"][0][0:2], ["6-0-1", "~"])
        self.assertEqual(datum_space["6-0-1"][0][2:], polygon_rows)

    def test_bulk_generation_writes_full_seta_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "precincts"
            generated = _MODULE.generate_precinct_sources(
                input_dir=SETA_INPUT_DIR,
                output_dir=output_dir,
                base_ruiqi_branch="247-17-77-0",
            )

            self.assertEqual(len(generated), 371)
            self.assertEqual(
                generated[0].name,
                "sc.3-2-3-17-77-1-6-4-1-4.cts.247_17_77_1.json",
            )
            self.assertEqual(
                generated[-1].name,
                "sc.3-2-3-17-77-1-6-4-1-4.cts.247_17_77_371.json",
            )

            sample_paths = [generated[0], generated[2], generated[-1]]
            for path in sample_paths:
                payload = json.loads(path.read_text(encoding="utf-8"))
                datum_space = dict(payload.get("datum_addressing_abstraction_space") or {})
                self.assertIn("6-0-1", datum_space)
                self.assertIn("7-3-1", datum_space)
                for address, row in datum_space.items():
                    if not address.startswith("4-"):
                        continue
                    declared = int(address.split("-")[1])
                    tokens = row[0]
                    observed = sum(1 for index, token in enumerate(tokens[:-1]) if token == "rf.3-1-1" and tokens[index + 1])
                    self.assertEqual(declared, observed, msg=f"{path.name}:{address}")


if __name__ == "__main__":
    unittest.main()
