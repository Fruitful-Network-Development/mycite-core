#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_metric(payload: dict[str, Any], metric_name: str) -> Any:
    if metric_name not in payload:
        raise KeyError(f"Metric '{metric_name}' is missing from {payload.get('schema') or 'payload'}")
    return payload[metric_name]


def _check_metric(category: str, metric_name: str, budget: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    actual = _resolve_metric(payload, metric_name)
    maximum = budget["max"]
    enforcement = str(budget.get("enforcement") or "hard")
    passed = actual <= maximum
    return {
      "category": category,
      "metric": metric_name,
      "actual": actual,
      "max": maximum,
      "enforcement": enforcement,
      "passed": passed,
      "evidence": budget.get("evidence") or "",
      "result": "pass" if passed else ("warn" if enforcement == "advisory" else "fail"),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check repo optimization budgets against generated benchmark artifacts.")
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[2],
        type=Path,
        help="Repository root containing benchmarks/ and MyCiteV2/.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path. Defaults to benchmarks/results/optimization_budget_check.json",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    repo_root = args.repo_root.resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from MyCiteV2.instances._shared.portal_host.app import build_shell_asset_manifest

    results_dir = repo_root / "benchmarks" / "results"
    budgets_path = repo_root / "benchmarks" / "budgets" / "optimization_budgets.json"
    output_path = Path(args.output).resolve() if args.output else results_dir / "optimization_budget_check.json"

    budgets_payload = _load_json(budgets_path)
    build_weight = _load_json(results_dir / "build_weight_baseline.json")
    interactions = _load_json(results_dir / "runtime_interactions_baseline.json")
    projection = _load_json(results_dir / "projection_serialization_baseline.json")
    test_tooling = _load_json(results_dir / "test_tooling_overhead_baseline.json")
    manifest = build_shell_asset_manifest(build_id="budget-check")
    manifest_budget = dict(manifest.get("budget_policy") or {})

    checks: list[dict[str, Any]] = []
    category_payloads = {
        "asset_size": build_weight,
        "interaction_latency": interactions,
        "projection_cpu": projection,
        "test_tooling": test_tooling,
    }
    for category, metric_budgets in dict(budgets_payload.get("budgets") or {}).items():
        payload = category_payloads[category]
        for metric_name, budget in dict(metric_budgets or {}).items():
            checks.append(_check_metric(category, metric_name, dict(budget or {}), payload))

    manifest_alignment = {
        "initial_load_gzip_bytes_max_matches_manifest": manifest_budget.get("initial_load_gzip_bytes_max")
        == budgets_payload["budgets"]["asset_size"]["initial_load_gzip_bytes"]["max"],
        "total_gzip_bytes_max_matches_manifest": manifest_budget.get("total_gzip_bytes_max")
        == budgets_payload["budgets"]["asset_size"]["total_gzip_bytes"]["max"],
        "deferred_gzip_bytes_max_matches_manifest": manifest_budget.get("deferred_gzip_bytes_max")
        == budgets_payload["budgets"]["asset_size"]["deferred_gzip_bytes"]["max"],
    }
    manifest_alignment["all"] = all(manifest_alignment.values())

    hard_failures = [check for check in checks if check["result"] == "fail"]
    advisory_warnings = [check for check in checks if check["result"] == "warn"]
    payload = {
        "schema": "mycite.benchmarks.optimization_budget_check.v1",
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "budgets_path": str(budgets_path),
        "results_dir": str(results_dir),
        "manifest_alignment": manifest_alignment,
        "checks": checks,
        "hard_failure_count": len(hard_failures),
        "advisory_warning_count": len(advisory_warnings),
        "status": "pass" if not hard_failures and manifest_alignment["all"] else "fail",
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(output_path))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
