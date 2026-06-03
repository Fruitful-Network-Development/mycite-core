"""C1 — the thin CTS-GIS tools (map / district / admin), read-only fast-read.

Contract tests + compiled-artifact map fast-read over a fixture, plus a guarded
live-MOS check (district/admin) and the perf canary that proves the map tool's
artifact read stays well under budget BEFORE the heavy runtime is deleted (C3).
"""

from __future__ import annotations

import json
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import WORKBENCH_UI_TOOL_ROUTE
from MyCiteV2.packages.tools import _cts_gis_artifact as artifact
from MyCiteV2.packages.tools import get
from MyCiteV2.packages.tools.cts_gis_admin import CtsGisAdminTool
from MyCiteV2.packages.tools.cts_gis_district import CtsGisDistrictTool
from MyCiteV2.packages.tools.cts_gis_map import CtsGisMapTool

_LIVE_DB = "/srv/webapps/mycite/fnd/private/mos_authority.sqlite3"
_LIVE_DATA_DIR = "/srv/webapps/mycite/fnd/data"
_TOOL_IDS = ("cts_gis", "cts_gis_district", "cts_gis_admin")
# The cts tools were RETIRED from the viz palette (no reliable per-doc eligibility — they
# render a doc-independent compiled artifact). The classes remain + their behavior is still
# tested directly; they are simply not in the registry.
_TOOLS = {"cts_gis": CtsGisMapTool(), "cts_gis_district": CtsGisDistrictTool(), "cts_gis_admin": CtsGisAdminTool()}


def _write_artifact(data_dir: Path, *, features: list[dict]) -> None:
    compiled = data_dir / "payloads" / "compiled"
    compiled.mkdir(parents=True, exist_ok=True)
    (compiled / "cts_gis.fnd.compiled.json").write_text(json.dumps({
        "projection_model": {
            "feature_collection": {"type": "FeatureCollection", "features": features},
            "feature_count": len(features),
            "focus_bounds": [0, 0, 1, 1],
            "projection_state": "ready",
        },
    }), encoding="utf-8")


class ContractTests(unittest.TestCase):
    def test_three_thin_tools_retired_from_palette_but_classes_intact(self) -> None:
        for tid in _TOOL_IDS:
            self.assertIsNone(get(tid), f"{tid} should be RETIRED from the viz palette")
            self.assertEqual(_TOOLS[tid].route, WORKBENCH_UI_TOOL_ROUTE, tid)

    def test_map_tool_no_longer_imports_the_slow_service(self) -> None:
        import MyCiteV2.packages.tools.cts_gis_map as m
        src = Path(m.__file__).read_text(encoding="utf-8")
        # No import of, or call into, the slow CtsGisReadOnlyService.read_projection_bundle
        # (docstring may name it in prose; the import/call must be gone).
        self.assertNotIn("cross_domain.cts_gis.service import", src)
        self.assertNotIn("read_projection_bundle(", src)


class MapProjectionFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = artifact._DATA_DIR

    def tearDown(self) -> None:
        artifact.configure_data_dir(self._saved)

    def test_map_reads_feature_collection_from_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            _write_artifact(data_dir, features=[{"type": "Feature", "id": "p1"}])
            artifact.configure_data_dir(data_dir)
            payload = _TOOLS["cts_gis"].build_panel_payload(
                authority_db_file=None, sandbox_id="cts_gis", document_id="d", datum_address="0-0-1",
            )
        self.assertEqual(payload["feature_count"], 1)
        self.assertEqual(payload["feature_collection"]["features"][0]["id"], "p1")
        self.assertEqual(payload["projection_state"], "ready")
        self.assertEqual(payload["diagnostics"]["source"], "compiled_artifact")

    def test_map_empty_when_artifact_absent(self) -> None:
        with TemporaryDirectory() as tmp:
            artifact.configure_data_dir(Path(tmp))  # no artifact written
            payload = _TOOLS["cts_gis"].build_panel_payload(
                authority_db_file=None, sandbox_id="cts_gis", document_id="", datum_address="",
            )
        self.assertNotIn("error", payload)
        self.assertEqual(payload["feature_count"], 0)
        self.assertEqual(payload["projection_state"], "empty")


@unittest.skipUnless(os.path.exists(_LIVE_DB), "live MOS db not present")
class LiveMosThinToolTests(unittest.TestCase):
    def test_district_tool_lists_member_precincts(self) -> None:
        payload = _TOOLS["cts_gis_district"].build_panel_payload(
            authority_db_file=Path(_LIVE_DB), sandbox_id="cts_gis", document_id="d", datum_address="0-0-1",
        )
        self.assertNotIn("error", payload)
        self.assertIsInstance(payload["member_precinct_ids"], list)
        self.assertEqual(payload["member_count"], len(payload["member_precinct_ids"]))

    def test_admin_tool_resolves_identity(self) -> None:
        payload = _TOOLS["cts_gis_admin"].build_panel_payload(
            authority_db_file=Path(_LIVE_DB), sandbox_id="cts_gis", document_id="d", datum_address="0-0-1",
        )
        self.assertNotIn("error", payload)
        self.assertIn("node_id", payload)


class MapPerfCanaryTests(unittest.TestCase):
    """The 504/OOM regression guard: the artifact fast-read must be fast — the slow
    read_projection_bundle was ~35s. Hermetic: times the compiled-artifact read over
    a seeded fixture (no live MOS), with a generous CI-safe ceiling that still catches
    the ~35s-class regression this canary exists to prevent. (Wall-clock micro-budgets
    are flaky under CI load, so the ceiling guards order-of-magnitude, not jitter.)"""

    _BUDGET_S = 2.0

    def setUp(self) -> None:
        self._saved = artifact._DATA_DIR
        self._tmp = TemporaryDirectory()
        data_dir = Path(self._tmp.name)
        # A non-trivial artifact so the read does real work, but still bounded.
        _write_artifact(data_dir, features=[
            {"type": "Feature", "id": f"p{i}", "geometry": {"type": "Point", "coordinates": [i, i]}}
            for i in range(200)
        ])
        artifact.configure_data_dir(data_dir)

    def tearDown(self) -> None:
        artifact.configure_data_dir(self._saved)
        self._tmp.cleanup()

    def test_map_build_panel_payload_under_budget(self) -> None:
        tool = _TOOLS["cts_gis"]
        # warm + measure (cached artifact read)
        tool.build_panel_payload(authority_db_file=None, sandbox_id="cts_gis", document_id="d", datum_address="0-0-1")
        start = time.perf_counter()
        payload = tool.build_panel_payload(authority_db_file=None, sandbox_id="cts_gis", document_id="d", datum_address="0-0-1")
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, self._BUDGET_S, f"map fast-read took {elapsed:.3f}s (budget {self._BUDGET_S}s)")
        self.assertNotIn("error", payload)
        self.assertEqual(payload["feature_count"], 200)


if __name__ == "__main__":
    unittest.main()
