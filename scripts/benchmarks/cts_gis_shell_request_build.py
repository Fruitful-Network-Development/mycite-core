from __future__ import annotations

import json
import math
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from MyCiteV2.packages.state_machine.portal_shell import (
    CTS_GIS_TOOL_SURFACE_ID,
    PortalScope,
    build_portal_shell_request_payload,
    initial_portal_shell_state,
)
from MyCiteV2.instances._shared.runtime import portal_cts_gis_runtime as cts_runtime

FIXTURE = ROOT / "benchmarks" / "data" / "cts_gis_projection_fixture_v1.json"
OUT_FILE = ROOT / "benchmarks" / "results" / "cts_gis_shell_request_build_report.json"


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1))
    return ordered[idx]


def _sample_tool_state(row_count: int) -> dict[str, object]:
    return {
        "nimm_directive": "nav",
        "active_path": ["3", "3-2", "3-2-3", "3-2-3-17", "3-2-3-17-77"],
        "selected_node_id": "3-2-3-17-77",
        "aitas": {
            "attention_node_id": "3-2-3-17-77",
            "intention_rule_id": "3-2-3-17-77-0-0",
            "time_directive": "4-447-751-507-819",
            "archetype_family_id": "25",
        },
        "source": {
            "attention_document_id": "sandbox:cts_gis:sc.3-2-3-17-77.json",
            "precinct_district_overlay_enabled": False,
        },
        "selection": {
            "selected_row_address": "7-3-1",
            "selected_feature_id": f"feature-{row_count}",
            "selected_row_explicit": True,
            "selected_feature_explicit": True,
        },
    }


def _legacy_request_builder(
    *,
    portal_scope: PortalScope,
    shell_state: object,
    tool_state: dict[str, object],
) -> dict[str, object]:
    request_body = build_portal_shell_request_payload(
        portal_scope=portal_scope,
        shell_state=shell_state,
        requested_surface_id=CTS_GIS_TOOL_SURFACE_ID,
    )
    request_body["tool_state"] = cts_runtime._tool_state_clone(tool_state)
    return request_body


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = list(fixture.get("rows") or [])
    row_count = len(rows)
    iterations = int(fixture.get("iterations") or 200)
    requests_per_iteration = max(50, row_count)
    total_requests = iterations * requests_per_iteration

    portal_scope = PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection"))
    shell_state = initial_portal_shell_state(surface_id=CTS_GIS_TOOL_SURFACE_ID, portal_scope=portal_scope)
    base_shell_request = build_portal_shell_request_payload(
        portal_scope=portal_scope,
        shell_state=shell_state,
        requested_surface_id=CTS_GIS_TOOL_SURFACE_ID,
    )

    legacy_timings_ms: list[float] = []
    templated_timings_ms: list[float] = []
    bytes_per_request: list[int] = []
    sample_tool_state = _sample_tool_state(row_count)

    for _ in range(iterations):
        start = time.perf_counter()
        for item_idx in range(requests_per_iteration):
            state = dict(sample_tool_state)
            selection = dict(sample_tool_state["selection"])
            selection["selected_feature_id"] = f"feature-{item_idx}"
            state["selection"] = selection
            payload = _legacy_request_builder(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=state,
            )
            bytes_per_request.append(len(json.dumps(payload, separators=(",", ":"), sort_keys=True)))
        legacy_timings_ms.append((time.perf_counter() - start) * 1000.0)

    for _ in range(iterations):
        start = time.perf_counter()
        for item_idx in range(requests_per_iteration):
            state = dict(sample_tool_state)
            selection = dict(sample_tool_state["selection"])
            selection["selected_feature_id"] = f"feature-{item_idx}"
            state["selection"] = selection
            cts_runtime._tool_state_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=state,
                base_shell_request=base_shell_request,
            )
        templated_timings_ms.append((time.perf_counter() - start) * 1000.0)

    legacy_median = statistics.median(legacy_timings_ms) if legacy_timings_ms else 0.0
    templated_median = statistics.median(templated_timings_ms) if templated_timings_ms else 0.0
    legacy_p95 = p95(legacy_timings_ms)
    templated_p95 = p95(templated_timings_ms)
    median_delta_ms = legacy_median - templated_median
    p95_delta_ms = legacy_p95 - templated_p95
    median_improvement_pct = (median_delta_ms / legacy_median * 100.0) if legacy_median > 0 else 0.0
    p95_improvement_pct = (p95_delta_ms / legacy_p95 * 100.0) if legacy_p95 > 0 else 0.0

    payload = {
        "schema": "mycite.benchmarks.cts_gis_shell_request_build.v1",
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "iterations": iterations,
        "requests_per_iteration": requests_per_iteration,
        "total_requests": total_requests,
        "legacy": {
            "median_iteration_ms": round(legacy_median, 3),
            "p95_iteration_ms": round(legacy_p95, 3),
        },
        "templated": {
            "median_iteration_ms": round(templated_median, 3),
            "p95_iteration_ms": round(templated_p95, 3),
        },
        "delta": {
            "median_iteration_ms": round(median_delta_ms, 3),
            "p95_iteration_ms": round(p95_delta_ms, 3),
            "median_improvement_pct": round(median_improvement_pct, 3),
            "p95_improvement_pct": round(p95_improvement_pct, 3),
        },
        "average_request_payload_bytes": round(statistics.mean(bytes_per_request) if bytes_per_request else 0.0, 3),
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(OUT_FILE))


if __name__ == "__main__":
    main()
