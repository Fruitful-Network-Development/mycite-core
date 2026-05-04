from __future__ import annotations

import ast
import json
import math
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = ROOT / "MyCiteV2" / "tests"
OUT_FILE = ROOT / "benchmarks" / "results" / "test_tooling_overhead_baseline.json"
SAMPLED_IMPORTS = (
    "MyCiteV2.instances._shared.runtime.portal_shell_runtime",
    "MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime",
    "MyCiteV2.tests.unit.test_cts_gis_compiled_runtime",
    "MyCiteV2.tests.unit.test_portal_workspace_runtime_behavior",
    "MyCiteV2.tests.contracts.test_contract_docs_alignment",
)
IMPORT_REPETITIONS = 3


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1))
    return ordered[idx]


def _measure_import_ms(module_name: str) -> list[float]:
    samples: list[float] = []
    for _ in range(IMPORT_REPETITIONS):
        started = time.perf_counter()
        subprocess.run(
            [sys.executable, "-c", f"import {module_name}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        samples.append((time.perf_counter() - started) * 1000.0)
    return samples


def _repeated_private_helpers() -> tuple[int, list[dict[str, object]]]:
    counts: dict[str, int] = {}
    for path in TESTS_ROOT.rglob("test_*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("_"):
                counts[node.name] = counts.get(node.name, 0) + 1
    repeated = [
        {"helper_name": name, "definition_count": count}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if count > 1
    ]
    return len(repeated), repeated[:20]


def main() -> None:
    imports: list[dict[str, object]] = []
    all_import_samples: list[float] = []
    for module_name in SAMPLED_IMPORTS:
        samples = _measure_import_ms(module_name)
        all_import_samples.extend(samples)
        imports.append(
            {
                "module": module_name,
                "samples_ms": [round(sample, 3) for sample in samples],
                "median_ms": round(statistics.median(samples), 3),
                "p95_ms": round(p95(samples), 3),
            }
        )

    repeated_count, repeated_helpers = _repeated_private_helpers()
    payload = {
        "schema": "mycite.benchmarks.test_tooling_overhead.v1",
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "sampled_import_count": len(imports),
        "import_repetitions": IMPORT_REPETITIONS,
        "sampled_imports": imports,
        "aggregate_import_median_ms": round(statistics.median(all_import_samples) if all_import_samples else 0.0, 3),
        "aggregate_import_p95_ms": round(p95(all_import_samples), 3),
        "test_file_count": sum(1 for _ in TESTS_ROOT.rglob("test_*.py")),
        "repeated_private_helper_name_count": repeated_count,
        "top_repeated_private_helpers": repeated_helpers,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(OUT_FILE))


if __name__ == "__main__":
    main()
