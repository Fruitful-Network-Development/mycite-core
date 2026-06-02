"""Square-packing geometry for farm field plots.

Pure geometry: given a field polygon (lon/lat), return the maximum set of equal,
axis-aligned squares of a fixed real-world edge length whose entire area lies
inside the polygon (none crossing the boundary). Used by the farm-profile viewer
(TASK-005, computed live) and the plot migration (TASK-006, persisted as HOPS
geometry inside farm_profile). See plans/TASK-003-farm-plot-model.md.

shapely is the only third-party dependency (2.1.2 in the fnd_portal venv). No
randomness — the grid-origin sweep is a deterministic scan so output is stable.
"""

from __future__ import annotations

import math

from shapely.geometry import Polygon, box

# WGS84 metres-per-degree of latitude (near-constant); longitude scales by cos(lat).
_M_PER_DEG_LAT = 111_320.0


def meters_to_degrees(edge_m: float, latitude: float) -> tuple[float, float]:
    """Convert a real-world edge length (metres) to (d_lon, d_lat) degrees at a
    given latitude, so the resulting cell is a real-world square (axis-aligned)."""
    d_lat = edge_m / _M_PER_DEG_LAT
    cos_lat = math.cos(math.radians(latitude))
    d_lon = edge_m / (_M_PER_DEG_LAT * cos_lat) if cos_lat else d_lat
    return d_lon, d_lat


def pack_squares(field: Polygon, edge_m: float, *, origin_steps: int = 5) -> list[Polygon]:
    """Return the maximal set of equal axis-aligned squares fully inside ``field``.

    ``edge_m`` is the fixed real-world square edge in metres (the operator's chosen
    plot size). The grid origin is swept over an ``origin_steps`` x ``origin_steps``
    sub-cell offset grid and the densest packing is kept — deterministic, so the
    same field + edge always yields the same squares. A square is kept only when
    ``field.covers(square)`` (entirely inside; edges may touch the boundary, none
    cross it). Output is sorted by (row, col) for stable downstream addressing.
    """
    if edge_m <= 0 or field is None or field.is_empty:
        return []
    min_x, min_y, max_x, max_y = field.bounds
    lat_mid = (min_y + max_y) / 2.0
    # Near the poles cos(lat)->0, so a metre maps to an unbounded span of longitude
    # and axis-aligned "squares" degenerate. Refuse rather than emit distorted cells.
    if abs(lat_mid) >= 89.9:
        return []
    d_lon, d_lat = meters_to_degrees(edge_m, lat_mid)
    if d_lon <= 0 or d_lat <= 0:
        return []

    steps = max(1, int(origin_steps))
    best: list[Polygon] = []
    for ox in range(steps):
        for oy in range(steps):
            start_x = min_x - d_lon * (ox / steps)
            start_y = min_y - d_lat * (oy / steps)
            n_cols = math.ceil((max_x - start_x) / d_lon) + 1
            n_rows = math.ceil((max_y - start_y) / d_lat) + 1
            squares: list[Polygon] = []
            for r in range(n_rows):
                y0 = start_y + r * d_lat
                for c in range(n_cols):
                    x0 = start_x + c * d_lon
                    cell = box(x0, y0, x0 + d_lon, y0 + d_lat)
                    if field.covers(cell):
                        squares.append(cell)
            if len(squares) > len(best):
                best = squares
    best.sort(key=lambda s: (round(s.bounds[1], 10), round(s.bounds[0], 10)))
    return best


def field_polygon_from_hops_tokens(tokens: list[str]) -> Polygon:
    """Decode a ring of HOPS coordinate tokens (rf.3-1-3 values) to a shapely
    Polygon in lon/lat. Raises ValueError if fewer than 3 vertices decode."""
    from MyCiteV2.packages.core.structures.hops import decode_hops_coordinate_token

    points: list[tuple[float, float]] = []
    for token in tokens:
        decoded = decode_hops_coordinate_token(token)
        if not decoded:
            continue
        points.append((decoded["longitude"]["value"], decoded["latitude"]["value"]))
    if len(points) < 3:
        raise ValueError("hops ring needs at least 3 decodable vertices")
    return Polygon(points)


def square_to_hops_tokens(square: Polygon) -> list[str]:
    """Encode a square's 4 corners (CCW, open ring) to HOPS coordinate tokens for
    persistence as a family-4 ring inside farm_profile (TASK-006)."""
    from MyCiteV2.scripts.cts_gis_geojson_hops_utils import encode_hops_coordinate

    corners = list(square.exterior.coords)[:4]  # exterior repeats the first point; drop it
    return [encode_hops_coordinate(float(lon), float(lat)) for lon, lat in corners]
