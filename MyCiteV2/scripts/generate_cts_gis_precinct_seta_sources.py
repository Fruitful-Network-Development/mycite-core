from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "personal_notes"
    / "CTS-GIS-prototype-mockup"
    / "precincts"
    / "247-17-77-0"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "deployed"
    / "fnd"
    / "data"
    / "sandbox"
    / "cts-gis"
    / "sources"
    / "precincts"
)
DEFAULT_BASE_RUIQI_BRANCH = "247-17-77-0"
ANCHOR_PREFIX = "sc.3-2-3-17-77-1-6-4-1-4"
ANCHOR_FILE_VERSION = "<hash here>"
SETA_FILENAME_PATTERN = re.compile(r"^setA__PRECINCT-(\d+)\.geojson$")
HOPS_PREFIX = ("3", "76")
HOPS_PARTITION_SEGMENT_COUNT = 16
HOPS_BUCKET_COUNT = 100
FILAMENT_BIT_LENGTH = 128


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _precinct_number_from_filename(path: Path) -> int:
    match = SETA_FILENAME_PATTERN.match(path.name)
    if match is None:
        raise ValueError(f"Expected setA precinct filename, got {path.name}")
    return int(match.group(1))


def _sorted_seta_geojson_paths(input_dir: Path) -> list[Path]:
    candidates = [path for path in input_dir.glob("setA__PRECINCT-*.geojson") if path.is_file()]
    return sorted(candidates, key=lambda path: (_precinct_number_from_filename(path), path.name))


def _load_single_feature(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    payload_type = _as_text(payload.get("type"))
    if payload_type == "Feature":
        feature = payload
    elif payload_type == "FeatureCollection":
        features = payload.get("features")
        if not isinstance(features, list) or len(features) != 1 or not isinstance(features[0], dict):
            raise ValueError(f"Expected one feature in {path}")
        feature = features[0]
    else:
        raise ValueError(f"Unsupported GeoJSON payload type in {path}: {payload_type or '<blank>'}")

    geometry = feature.get("geometry")
    if not isinstance(geometry, dict):
        raise ValueError(f"Feature geometry missing in {path}")
    geometry_type = _as_text(geometry.get("type"))
    if geometry_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError(f"Unsupported geometry type in {path}: {geometry_type or '<blank>'}")

    properties = feature.get("properties")
    if not isinstance(properties, dict):
        raise ValueError(f"Feature properties missing in {path}")
    precinct_name = _as_text(properties.get("PrecinctNa"))
    if not precinct_name:
        raise ValueError(f"PrecinctNa missing in {path}")

    return {
        "type": "Feature",
        "properties": properties,
        "geometry": geometry,
    }


def _normalize_ring(ring: Any) -> list[list[float]]:
    if not isinstance(ring, list):
        raise ValueError("Expected ring coordinate list")
    normalized = [
        [float(point[0]), float(point[1])]
        for point in ring
        if isinstance(point, list) and len(point) >= 2
    ]
    if not normalized:
        raise ValueError("Expected at least one valid coordinate in ring")
    if normalized[0] != normalized[-1]:
        normalized.append(list(normalized[0]))
    return normalized


def _geometry_polygons(geometry: dict[str, Any]) -> list[list[list[list[float]]]]:
    geometry_type = _as_text(geometry.get("type"))
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list):
        raise ValueError(f"Expected coordinates list for {geometry_type or 'geometry'}")
    if geometry_type == "Polygon":
        polygons = [coordinates]
    elif geometry_type == "MultiPolygon":
        polygons = coordinates
    else:
        raise ValueError(f"Unsupported geometry type: {geometry_type or '<blank>'}")

    normalized_polygons: list[list[list[list[float]]]] = []
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise ValueError("Expected polygon ring list")
        normalized_polygons.append([_normalize_ring(ring) for ring in polygon])
    return normalized_polygons


def encode_hops_coordinate(longitude: float, latitude: float) -> str:
    lon_min = -180.0
    lon_max = 180.0
    lat_min = -90.0
    lat_max = 90.0
    parts = [*HOPS_PREFIX]

    for index in range(HOPS_PARTITION_SEGMENT_COUNT):
        if index % 2 == 0:
            span = (lon_max - lon_min) / HOPS_BUCKET_COUNT
            bucket = math.floor((float(longitude) - lon_min) / span)
            bucket = max(0, min(HOPS_BUCKET_COUNT - 1, bucket))
            lon_min = lon_min + (span * bucket)
            lon_max = lon_min + span
        else:
            span = (lat_max - lat_min) / HOPS_BUCKET_COUNT
            bucket = math.floor((float(latitude) - lat_min) / span)
            bucket = max(0, min(HOPS_BUCKET_COUNT - 1, bucket))
            lat_min = lat_min + (span * bucket)
            lat_max = lat_min + span
        parts.append(str(bucket))

    return "-".join(parts)


def encode_precinct_name_bits(name: str) -> str:
    if any(ord(character) > 127 for character in name):
        raise ValueError(f"Precinct name must be ASCII, got {name!r}")
    bitstring = "".join(f"{ord(character):08b}" for character in name)
    if len(bitstring) > FILAMENT_BIT_LENGTH:
        raise ValueError(
            f"Precinct name exceeds {FILAMENT_BIT_LENGTH // 8} ASCII characters: {name!r}"
        )
    return bitstring.ljust(FILAMENT_BIT_LENGTH, "0")


def _ruiqi_id_for_sequence(base_ruiqi_branch: str, sequence_index: int) -> str:
    base = _as_text(base_ruiqi_branch)
    if base.endswith("-0"):
        return f"{base[:-2]}-{sequence_index}"
    return f"{base}-{sequence_index}"


def _ruiqi_underscored(ruiqi_id: str) -> str:
    return ruiqi_id.replace("-", "_")


def _cts_filename(ruiqi_id: str) -> str:
    return f"{ANCHOR_PREFIX}.cts.{_ruiqi_underscored(ruiqi_id)}.json"


def build_precinct_payload(feature: dict[str, Any], *, ruiqi_id: str) -> dict[str, Any]:
    geometry = dict(feature.get("geometry") or {})
    precinct_name = _as_text((feature.get("properties") or {}).get("PrecinctNa"))
    if not precinct_name:
        raise ValueError("PrecinctNa missing from feature properties")

    datum_space: dict[str, list[Any]] = {}
    ring_sequence = 0
    polygon_addresses: list[str] = []
    ruiqi_underscored = _ruiqi_underscored(ruiqi_id)

    for polygon_sequence, polygon in enumerate(_geometry_polygons(geometry), start=1):
        ring_addresses: list[str] = []
        for ring in polygon:
            ring_sequence += 1
            tokens = [encode_hops_coordinate(longitude, latitude) for longitude, latitude in ring]
            row_address = f"4-{len(tokens)}-{ring_sequence}"
            row_tokens: list[str] = [row_address]
            for token in tokens:
                row_tokens.extend(["rf.3-1-1", token])
            datum_space[row_address] = [
                row_tokens,
                [f"polygon_{ring_sequence}"],
            ]
            ring_addresses.append(row_address)

        polygon_address = f"5-0-{polygon_sequence}"
        datum_space[polygon_address] = [
            [polygon_address, "~", *ring_addresses],
            [f"precinct_{ruiqi_underscored}_polygon_{polygon_sequence}"],
        ]
        polygon_addresses.append(polygon_address)

    datum_space["6-0-1"] = [
        ["6-0-1", "~", *polygon_addresses],
        [f"precinct_{ruiqi_underscored}_boundary_collection"],
    ]
    datum_space["7-3-1"] = [
        [
            "7-3-1",
            "rf.3-1-4",
            ruiqi_id,
            "rf.3-1-5",
            encode_precinct_name_bits(precinct_name),
            "6-0-1",
            "1",
        ],
        [f"precinct_{ruiqi_underscored}"],
    ]

    return {
        "anchor_file_version": ANCHOR_FILE_VERSION,
        "datum_addressing_abstraction_space": datum_space,
    }


def generate_precinct_sources(
    *,
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    base_ruiqi_branch: str = DEFAULT_BASE_RUIQI_BRANCH,
) -> list[Path]:
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_paths: list[Path] = []
    for sequence_index, source_path in enumerate(_sorted_seta_geojson_paths(input_dir), start=1):
        feature = _load_single_feature(source_path)
        ruiqi_id = _ruiqi_id_for_sequence(base_ruiqi_branch, sequence_index)
        output_path = output_dir / _cts_filename(ruiqi_id)
        payload = build_precinct_payload(feature, ruiqi_id=ruiqi_id)
        _write_json(output_path, payload)
        generated_paths.append(output_path)

    return generated_paths


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate staged CTS-GIS setA precinct source files."
    )
    parser.add_argument(
        "--input-dir",
        default=str(DEFAULT_INPUT_DIR),
        help="Directory containing setA precinct GeoJSON files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where staged precinct .cts. datum files will be written.",
    )
    parser.add_argument(
        "--base-ruiqi-branch",
        default=DEFAULT_BASE_RUIQI_BRANCH,
        help="Base Ruiqi branch used to derive per-precinct child ids.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    generated = generate_precinct_sources(
        input_dir=Path(args.input_dir),
        output_dir=Path(args.output_dir),
        base_ruiqi_branch=_as_text(args.base_ruiqi_branch) or DEFAULT_BASE_RUIQI_BRANCH,
    )
    print(f"Generated {len(generated)} staged setA precinct source files in {Path(args.output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
