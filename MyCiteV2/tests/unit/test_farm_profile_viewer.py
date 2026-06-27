from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.datum_ops.datum_resolve import (
    decode_label as _decode_title_bits,
)
from MyCiteV2.packages.core.datum_ops.datum_resolve import (
    resolve_coordinate as _ring_coords,
)
from MyCiteV2.packages.tools import get as tools_get
from MyCiteV2.packages.tools.farm_profile_viewer import (
    FarmProfileViewer,
    _feature,
)

_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")


class TestFarmProfilePureHelpers(unittest.TestCase):
    def test_registered(self) -> None:
        self.assertIsInstance(tools_get("farm_profile"), FarmProfileViewer)
        self.assertEqual(FarmProfileViewer.applies_to_archetype, ("hops_geospatial_filament",))

    def test_ring_coords_decodes_hops(self) -> None:
        # A family-4 head with two rf.3-1-3 HOPS tokens.
        from MyCiteV2.packages.core.structures.hops import decode_hops_coordinate_token
        from MyCiteV2.scripts.cts_gis_geojson_hops_utils import encode_hops_coordinate

        t1 = encode_hops_coordinate(-81.52, 41.236)
        t2 = encode_hops_coordinate(-81.51, 41.240)
        head = ["4-2-1", "rf.3-1-3", t1, "rf.3-1-3", t2]
        coords = _ring_coords(head)
        self.assertEqual(len(coords), 2)
        d1 = decode_hops_coordinate_token(t1)
        self.assertAlmostEqual(coords[0][0], d1["longitude"]["value"], places=9)

    def test_feature_closes_ring_and_tags_kind(self) -> None:
        coords = [(-81.52, 41.236), (-81.51, 41.236), (-81.51, 41.240)]
        feat = _feature(coords, kind="plot", label="plot_1", fid="x:5-0-4")
        self.assertEqual(feat["properties"]["kind"], "plot")
        self.assertEqual(feat["geometry"]["type"], "Polygon")
        ring = feat["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1], "GeoJSON polygon ring must be closed")

    def test_feature_rejects_degenerate(self) -> None:
        self.assertIsNone(_feature([(0, 0), (1, 1)], kind="field", label="x", fid="y"))

    def test_decode_title_bits(self) -> None:
        bits = "".join(format(ord(c), "08b") for c in "plot_1")
        self.assertEqual(_decode_title_bits(bits), "plot_1")


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestFarmProfileViewerLive(unittest.TestCase):
    def test_payload_shape_on_live_farm_profile(self) -> None:
        payload = FarmProfileViewer().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="", datum_address=""
        )
        self.assertIsNone(payload.get("error"))
        self.assertEqual(payload["schema"], "mycite.v2.portal.workbench.tool.farm_profile.v1")
        features = payload["feature_collection"]["features"]
        kinds = {f["properties"]["kind"] for f in features}
        self.assertIn("parcel", kinds, "must project the parcels")
        self.assertIn("field", kinds, "must project the field inside the largest parcel")
        self.assertIn("plot", kinds, "must show plot squares tiling the field")
        self.assertEqual(payload["feature_count"], len(features))
        # Every projected polygon is a closed GeoJSON ring with >= 4 positions.
        for f in features:
            ring = f["geometry"]["coordinates"][0]
            self.assertGreaterEqual(len(ring), 4)
            self.assertEqual(ring[0], ring[-1])
        labels = {fld["label"] for fld in payload["fields"]}
        self.assertTrue({"title", "parcels", "field", "plots", "plots_source"} <= labels)


if __name__ == "__main__":
    unittest.main()
