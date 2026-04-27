#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATIC_DIR="${ROOT_DIR}/MyCiteV2/instances/_shared/portal_host/static"
RESULTS_DIR="${ROOT_DIR}/benchmarks/results"
OUT_FILE="${RESULTS_DIR}/build_weight_baseline.json"

mkdir -p "${RESULTS_DIR}"

python3 - <<'PY' "${STATIC_DIR}" "${OUT_FILE}"
import importlib.util
import gzip
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

static_dir = Path(sys.argv[1])
out_file = Path(sys.argv[2])

root_dir = static_dir.parents[4]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

try:
    import brotli  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    brotli = None

from MyCiteV2.instances._shared.portal_host.app import build_shell_asset_manifest

manifest = build_shell_asset_manifest(build_id="benchmark")
scripts = dict(manifest.get("scripts") or {})
shell_modules = list(scripts.get("shell_modules") or [])
startup_module_ids = [
    str(entry.get("module_id") or "")
    for entry in shell_modules
    if str(entry.get("load_phase") or "").strip() != "deferred"
]
deferred_module_ids = [
    str(entry.get("module_id") or "")
    for entry in shell_modules
    if str(entry.get("load_phase") or "").strip() == "deferred"
]
startup_files = {
    str(scripts.get("portal_js", {}).get("file") or ""),
    str(scripts.get("shell_entry", {}).get("file") or ""),
    *[
        str(entry.get("file") or "")
        for entry in shell_modules
        if str(entry.get("load_phase") or "").strip() != "deferred"
    ],
}
startup_files.discard("")

files = sorted(static_dir.glob("*.js"))
rows = []
for path in files:
    raw = path.read_bytes()
    gz = gzip.compress(raw)
    br = brotli.compress(raw) if brotli is not None else b""
    rows.append(
        {
            "path": str(path),
            "name": path.name,
            "raw_bytes": len(raw),
            "gzip_bytes": len(gz),
            "brotli_bytes": len(br) if brotli is not None else None,
            "initial_load": path.name in startup_files,
        }
    )

rows_by_raw = sorted(rows, key=lambda item: item["raw_bytes"], reverse=True)
rows_by_gzip = sorted(rows, key=lambda item: item["gzip_bytes"], reverse=True)
rows_by_brotli = sorted(
    rows,
    key=lambda item: item["brotli_bytes"] if isinstance(item.get("brotli_bytes"), int) else -1,
    reverse=True,
)
initial_rows = [item for item in rows if item["initial_load"]]
deferred_rows = [item for item in rows if not item["initial_load"]]
initial_by_gzip = sorted(initial_rows, key=lambda item: item["gzip_bytes"], reverse=True)

def total_brotli(items):
    values = [item.get("brotli_bytes") for item in items if isinstance(item.get("brotli_bytes"), int)]
    return sum(values) if values else None

def git_revision() -> str:
    head = root_dir / ".git"
    if not head.exists():
        return ""
    import subprocess
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return ""
    return completed.stdout.strip()

payload = {
    "schema": "mycite.benchmarks.build_weight.v1",
    "generated_at_utc": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
    "git_revision": git_revision(),
    "environment": {
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
    },
    "files_analyzed": len(rows),
    "total_raw_bytes": sum(item["raw_bytes"] for item in rows),
    "total_gzip_bytes": sum(item["gzip_bytes"] for item in rows),
    "total_brotli_bytes": total_brotli(rows),
    "initial_load_raw_bytes": sum(item["raw_bytes"] for item in initial_rows),
    "initial_load_gzip_bytes": sum(item["gzip_bytes"] for item in initial_rows),
    "initial_load_brotli_bytes": total_brotli(initial_rows),
    "deferred_raw_bytes": sum(item["raw_bytes"] for item in deferred_rows),
    "deferred_gzip_bytes": sum(item["gzip_bytes"] for item in deferred_rows),
    "deferred_brotli_bytes": total_brotli(deferred_rows),
    "startup_module_ids": startup_module_ids,
    "deferred_module_ids": deferred_module_ids,
    "top5_raw": rows_by_raw[:5],
    "top5_gzip": rows_by_gzip[:5],
    "top5_brotli": rows_by_brotli[:5] if brotli is not None else [],
    "top5_initial_gzip": initial_by_gzip[:5],
}
out_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(str(out_file))
PY
