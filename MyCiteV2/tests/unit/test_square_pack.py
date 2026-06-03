from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shapely.geometry import Polygon

from MyCiteV2.packages.core.hops.square_pack import (
    meters_to_degrees,
    pack_squares,
    square_to_hops_tokens,
)
from MyCiteV2.packages.core.structures.hops import decode_hops_coordinate_token

# The live agro_erp farm_profile parcel_1 outer ring (4-29-1), decoded to lon/lat
# (read-back 2026-06-02). ~800 m across in Summit County, Ohio.
PARCEL_1 = [
    (-81.519243306, 41.2358431405), (-81.5192077635, 41.240386448),
    (-81.5208272952, 41.2403471539), (-81.5223023446, 41.240311345),
    (-81.524273366, 41.238523911), (-81.526692561, 41.2385314602),
    (-81.5274180211, 41.2385337141), (-81.5274897614, 41.2355360559),
    (-81.527457952, 41.2355309117), (-81.5272304527, 41.2354988015),
    (-81.5270025189, 41.2354684999), (-81.5266417169, 41.2354905685),
    (-81.5262771222, 41.2353705249), (-81.5260239954, 41.2353363349),
    (-81.5259168111, 41.2353148451), (-81.5258118638, 41.2352877835),
    (-81.5257096622, 41.2352552805), (-81.5256107015, 41.2352174942),
    (-81.5248421215, 41.2349538988), (-81.5231359133, 41.2343476921),
    (-81.5224764738, 41.2341463354), (-81.5223210192, 41.2341638069),
    (-81.5221793987, 41.2340169621), (-81.5218324434, 41.2338878367),
    (-81.5213051917, 41.233707396), (-81.5204469233, 41.2334746289),
    (-81.5200574226, 41.2333636127), (-81.5193065203, 41.2331752544),
    (-81.5193059638, 41.2331987626),
]


class TestMetersToDegrees(unittest.TestCase):
    def test_latitude_constant(self) -> None:
        d_lon, d_lat = meters_to_degrees(111_320.0, 0.0)
        self.assertAlmostEqual(d_lat, 1.0, places=6)
        self.assertAlmostEqual(d_lon, 1.0, places=6)  # cos(0) == 1

    def test_longitude_widens_with_latitude(self) -> None:
        _, d_lat = meters_to_degrees(30.0, 41.0)
        d_lon, _ = meters_to_degrees(30.0, 41.0)
        self.assertGreater(d_lon, d_lat)  # cos(41°) < 1 -> more degrees per metre east-west


class TestPackSquares(unittest.TestCase):
    def setUp(self) -> None:
        self.field = Polygon(PARCEL_1)

    def test_all_squares_fully_inside(self) -> None:
        squares = pack_squares(self.field, edge_m=30.0)
        self.assertGreater(len(squares), 0, "expected at least one 30 m plot in the field")
        for sq in squares:
            self.assertTrue(self.field.covers(sq), "every square must lie fully inside the field")

    def test_no_overlap_between_squares(self) -> None:
        squares = pack_squares(self.field, edge_m=30.0)
        for i in range(len(squares)):
            for j in range(i + 1, len(squares)):
                inter = squares[i].intersection(squares[j]).area
                self.assertLess(inter, 1e-12, "grid squares must not overlap")

    def test_deterministic(self) -> None:
        a = pack_squares(self.field, edge_m=30.0)
        b = pack_squares(self.field, edge_m=30.0)
        self.assertEqual(len(a), len(b))
        self.assertEqual(
            [s.bounds for s in a],
            [s.bounds for s in b],
            "packing must be deterministic (same field+edge -> identical squares)",
        )

    def test_larger_edge_yields_fewer_squares(self) -> None:
        small = pack_squares(self.field, edge_m=30.0)
        large = pack_squares(self.field, edge_m=80.0)
        self.assertGreaterEqual(len(small), len(large))

    def test_squares_are_equal_size(self) -> None:
        squares = pack_squares(self.field, edge_m=30.0)
        areas = {round(s.area, 14) for s in squares}
        self.assertEqual(len(areas), 1, "all plots must be equal-sized squares")

    def test_empty_for_nonpositive_edge(self) -> None:
        self.assertEqual(pack_squares(self.field, edge_m=0.0), [])
        self.assertEqual(pack_squares(self.field, edge_m=-5.0), [])

    def test_empty_near_the_pole(self) -> None:
        # Near the poles cos(lat)->0 and axis-aligned squares degenerate; pack refuses
        # rather than emitting wildly distorted cells.
        polar = Polygon([(0.0, 89.95), (0.001, 89.95), (0.001, 89.96), (0.0, 89.96)])
        self.assertEqual(pack_squares(polar, edge_m=30.0), [])

    def test_hops_roundtrip_of_a_plot_square(self) -> None:
        squares = pack_squares(self.field, edge_m=30.0)
        sq = squares[0]
        tokens = square_to_hops_tokens(sq)
        self.assertEqual(len(tokens), 4)
        corners = list(sq.exterior.coords)[:4]
        for token, (lon, lat) in zip(tokens, corners, strict=True):
            decoded = decode_hops_coordinate_token(token)
            self.assertIsNotNone(decoded)
            # HOPS is a 16-segment mixed-radix grid -> sub-metre cell; expect ~5 dp.
            self.assertAlmostEqual(decoded["longitude"]["value"], lon, places=4)
            self.assertAlmostEqual(decoded["latitude"]["value"], lat, places=4)


if __name__ == "__main__":
    unittest.main()
