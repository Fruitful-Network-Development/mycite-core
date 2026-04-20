#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FIXTURE="${ROOT_DIR}/benchmarks/data/interaction_journeys_v1.json"
RESULTS_DIR="${ROOT_DIR}/benchmarks/results"
OUT_FILE="${RESULTS_DIR}/runtime_interactions_baseline.json"

mkdir -p "${RESULTS_DIR}"

python3 - <<'PY' "${FIXTURE}" "${OUT_FILE}"
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

fixture_path = Path(sys.argv[1])
out_file = Path(sys.argv[2])
fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

def p95(values):
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    idx = max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1))
    return ordered[idx]

journeys = fixture.get("journeys") or []
all_samples = []
for journey in journeys:
    all_samples.extend(list(journey.get("durations_ms") or []))

long_tasks = list(fixture.get("startup_long_tasks_ms") or [])
payload = {
    "schema": "mycite.benchmarks.runtime_interactions.v1",
    "generated_at_utc": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
    "journey_count": len(journeys),
    "sample_count": len(all_samples),
    "p95_interaction_ms": round(p95(all_samples), 3),
    "median_interaction_ms": round(statistics.median(all_samples) if all_samples else 0.0, 3),
    "startup_long_task_count": len(long_tasks),
    "startup_long_task_p95_ms": round(p95(long_tasks), 3),
}
out_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(str(out_file))
PY

