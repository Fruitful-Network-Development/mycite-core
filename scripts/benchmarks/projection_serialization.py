from __future__ import annotations

import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "benchmarks" / "data" / "cts_gis_projection_fixture_v1.json"
OUT_FILE = ROOT / "benchmarks" / "results" / "projection_serialization_baseline.json"


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1))
    return ordered[idx]


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = list(fixture.get("rows") or [])
    iterations = int(fixture.get("iterations") or 200)
    timings_ms: list[float] = []
    bytes_per_iteration: list[int] = []

    for _ in range(iterations):
        start = time.perf_counter()
        packed = json.dumps(rows, separators=(",", ":"), sort_keys=True)
        unpacked = json.loads(packed)
        transformed = [
            {
                "node_id": str(item.get("node_id") or ""),
                "title": str(item.get("title") or ""),
                "has_geometry": bool(item.get("geometry")),
                "point_count": int(item.get("point_count") or 0),
            }
            for item in unpacked
        ]
        _ = json.dumps(transformed, separators=(",", ":"))
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        timings_ms.append(elapsed_ms)
        bytes_per_iteration.append(len(packed))

    payload = {
        "schema": "mycite.benchmarks.projection_serialization.v1",
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "fixture_rows": len(rows),
        "iterations": iterations,
        "median_iteration_ms": round(statistics.median(timings_ms) if timings_ms else 0.0, 3),
        "p95_iteration_ms": round(p95(timings_ms), 3),
        "average_payload_bytes": round(statistics.mean(bytes_per_iteration) if bytes_per_iteration else 0.0, 3),
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(OUT_FILE))


if __name__ == "__main__":
    main()

