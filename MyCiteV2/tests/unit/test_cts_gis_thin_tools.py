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

_LIVE_DB = "/srv/webapps/mycite/fnd/private/mos_authority.sqlite3"
_LIVE_DATA_DIR = "/srv/webapps/mycite/fnd/data"
_TOOL_IDS = ("cts_gis", "cts_gis_district", "cts_gis_admin")


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
    def test_three_thin_tools_registered_at_the_unified_route(self) -> None:
        for tid in _TOOL_IDS:
            tool = get(tid)
            self.assertIsNotNone(tool, tid)
            self.assertEqual(tool.route, WORKBENCH_UI_TOOL_ROUTE, tid)
            self.assertEqual(tool.applies_to_archetype, ("samras_family",), tid)

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
            payload = get("cts_gis").build_panel_payload(
                authority_db_file=None, sandbox_id="cts_gis", document_id="d", datum_address="0-0-1",
            )
        self.assertEqual(payload["feature_count"], 1)
        self.assertEqual(payload["feature_collection"]["features"][0]["id"], "p1")
        self.assertEqual(payload["projection_state"], "ready")
        self.assertEqual(payload["diagnostics"]["source"], "compiled_artifact")

    def test_map_empty_when_artifact_absent(self) -> None:
        with TemporaryDirectory() as tmp:
            artifact.configure_data_dir(Path(tmp))  # no artifact written
            payload = get("cts_gis").build_panel_payload(
                authority_db_file=None, sandbox_id="cts_gis", document_id="", datum_address="",
            )
        self.assertNotIn("error", payload)
        self.assertEqual(payload["feature_count"], 0)
        self.assertEqual(payload["projection_state"], "empty")


@unittest.skipUnless(os.path.exists(_LIVE_DB), "live MOS db not present")
class LiveMosThinToolTests(unittest.TestCase):
    def test_district_tool_lists_member_precincts(self) -> None:
        payload = get("cts_gis_district").build_panel_payload(
            authority_db_file=Path(_LIVE_DB), sandbox_id="cts_gis", document_id="d", datum_address="0-0-1",
        )
        self.assertNotIn("error", payload)
        self.assertIsInstance(payload["member_precinct_ids"], list)
        self.assertEqual(payload["member_count"], len(payload["member_precinct_ids"]))

    def test_admin_tool_resolves_identity(self) -> None:
        payload = get("cts_gis_admin").build_panel_payload(
            authority_db_file=Path(_LIVE_DB), sandbox_id="cts_gis", document_id="d", datum_address="0-0-1",
        )
        self.assertNotIn("error", payload)
        self.assertIn("node_id", payload)


@unittest.skipUnless(
    os.path.exists(_LIVE_DB) and os.path.isdir(_LIVE_DATA_DIR),
    "live MOS db + data dir not present",
)
class MapPerfCanaryTests(unittest.TestCase):
    """The 504/OOM regression guard: the artifact fast-read must be fast — the slow
    read_projection_bundle was ~35s. This must stay green before C3 deletes it."""

    def setUp(self) -> None:
        self._saved = artifact._DATA_DIR
        artifact.configure_data_dir(_LIVE_DATA_DIR)

    def tearDown(self) -> None:
        artifact.configure_data_dir(self._saved)

    def test_map_build_panel_payload_under_budget(self) -> None:
        tool = get("cts_gis")
        # warm + measure (cached artifact read)
        tool.build_panel_payload(authority_db_file=Path(_LIVE_DB), sandbox_id="cts_gis", document_id="", datum_address="")
        start = time.perf_counter()
        payload = tool.build_panel_payload(authority_db_file=Path(_LIVE_DB), sandbox_id="cts_gis", document_id="", datum_address="")
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.3, f"map fast-read took {elapsed:.3f}s (budget 0.3s)")
        self.assertNotIn("error", payload)


if __name__ == "__main__":
    unittest.main()
