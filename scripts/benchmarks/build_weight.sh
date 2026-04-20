#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATIC_DIR="${ROOT_DIR}/MyCiteV2/instances/_shared/portal_host/static"
RESULTS_DIR="${ROOT_DIR}/benchmarks/results"
OUT_FILE="${RESULTS_DIR}/build_weight_baseline.json"

mkdir -p "${RESULTS_DIR}"

python3 - <<'PY' "${STATIC_DIR}" "${OUT_FILE}"
import gzip
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

static_dir = Path(sys.argv[1])
out_file = Path(sys.argv[2])

files = sorted(static_dir.glob("*.js"))
rows = []
for path in files:
    raw = path.read_bytes()
    gz = gzip.compress(raw)
    rows.append(
        {
            "path": str(path),
            "name": path.name,
            "raw_bytes": len(raw),
            "gzip_bytes": len(gz),
        }
    )

rows_by_raw = sorted(rows, key=lambda item: item["raw_bytes"], reverse=True)
rows_by_gzip = sorted(rows, key=lambda item: item["gzip_bytes"], reverse=True)

payload = {
    "schema": "mycite.benchmarks.build_weight.v1",
    "generated_at_utc": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
    "files_analyzed": len(rows),
    "total_raw_bytes": sum(item["raw_bytes"] for item in rows),
    "total_gzip_bytes": sum(item["gzip_bytes"] for item in rows),
    "top5_raw": rows_by_raw[:5],
    "top5_gzip": rows_by_gzip[:5],
}
out_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(str(out_file))
PY

