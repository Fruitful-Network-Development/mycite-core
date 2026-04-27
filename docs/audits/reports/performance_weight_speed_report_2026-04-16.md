# Performance Weight/Speed Static Audit Report

Date: 2026-04-16

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-27`

Source plan: `docs/audits/performance_weight_speed_audit_plan_2026-04-16.md`.

## Planning Registry

- Stream ID: `STREAM-PERFORMANCE`
- Primary tasks:
  - `TASK-PERF-001` (blocked on approval gate)
  - `TASK-PERF-002` (measurement tables)
  - `TASK-PERF-003` (machine-readable budgets)
  - `TASK-PERF-004` (approval acknowledgments)
- Related optimization tasks:
  - `TASK-CODE-BLOAT-REMEDIATION-005`
  - `TASK-CODE-BLOAT-REMEDIATION-007`

## Measured Tables

### Build / Weight

| Metric | Historical baseline | 2026-04-27 measured | Delta | Rule / status |
| --- | ---: | ---: | ---: | --- |
| Initial JS raw bytes | `221,798 B` | `167,500 B` | `-24.5%` | improved |
| Initial JS gzip bytes | `45,606 B` | `35,488 B` | `-22.2%` | hard budget pass (`<= 41,000`) |
| Total JS gzip bytes | `not previously hard-gated` | `64,781 B` | `n/a` | hard budget pass (`<= 65,000`) |
| Deferred JS gzip bytes | `not previously budgeted` | `29,293 B` | `n/a` | advisory budget pass (`<= 30,000`) |
| Largest startup asset gzip | `v2_portal_inspector_renderers.js (historical startup hotspot)` | `portal.js 7,010 B` | shifted off startup path | improved |

Measured from:

- `benchmarks/results/build_weight_baseline.json`
- `benchmarks/results/optimization_budget_check.json`

### Runtime / Interaction

| Metric | Baseline | 2026-04-27 measured | Delta | Rule / status |
| --- | ---: | ---: | ---: | --- |
| p95 interaction latency | `136.0 ms` | `136.0 ms` | `0.0%` | no-regression pass |
| Median interaction latency | `110.5 ms` | `110.5 ms` | `0.0%` | tracked |
| Startup long task p95 | `61.0 ms` | `61.0 ms` | `0.0%` | hard budget pass (`<= 64.1`) |
| Live FND `/portal/healthz` median | `n/a` | `14.339 ms` | `n/a` | probe only |

Measured from:

- `benchmarks/results/runtime_interactions_baseline.json`
- `benchmarks/results/portal_healthz_probe_2026-04-27.json`

### Projection / Serialization

| Metric | Historical baseline | 2026-04-27 measured | Delta | Rule / status |
| --- | ---: | ---: | ---: | --- |
| Median iteration CPU | `0.039 ms` | `0.066 ms` | `+69.2%` | tracked; still sub-millisecond |
| p95 iteration CPU | `0.103 ms` | `0.105 ms` | `+1.9%` | no-regression pass (`<= 0.111`) |
| Average payload bytes | `425 B` | `425 B` | `0.0%` | advisory pass (`<= 450`) |

Measured from:

- `benchmarks/results/projection_serialization_baseline.json`
- `benchmarks/results/optimization_budget_check.json`

### Test / Tooling Overhead

| Metric | 2026-04-27 measured | Budget | Rule / status |
| --- | ---: | ---: | --- |
| Aggregate import median | `345.838 ms` baseline, `384.0 ms` rerun | `400.0 ms` | advisory budget pass |
| Aggregate import p95 | `503.059 ms` baseline, `632.918 ms` rerun | `650.0 ms` | advisory budget pass |
| Repeated private helper name count | `14` | `14` | advisory pass |

Measured from:

- `benchmarks/results/test_tooling_overhead_baseline.json`
- `benchmarks/results/optimization_budget_check.json`

## Ranked Backlog Refresh

| Rank | Item | Status | Evidence |
| ---: | --- | --- | --- |
| 1 | Shell asset manifest decomposition with deferred CTS-GIS inspector loading | completed | `code_bloat_frontend_bundle_findings_2026-04-27.md` |
| 2 | Canonical runtime normalization layer for request/query/action shaping | completed | `code_bloat_normalization_drift_findings_2026-04-27.md` |
| 3 | Machine-readable optimization budgets and regression gate | completed | `scripts/benchmarks/check_optimization_budgets.py` |
| 4 | Compile-before-deploy CTS-GIS posture and strict freshness enforcement | completed | `cts_gis_runtime_readiness_report_2026-04-25.md` |
| 5 | Performance approval gate acknowledgments | blocked | explicit owner sign-off still pending |

## Budget Automation

Machine-readable budget surfaces:

- `benchmarks/budgets/optimization_budgets.json`
- `scripts/benchmarks/check_optimization_budgets.py`
- `benchmarks/results/optimization_budget_check.json`

Current result:

- `status=pass`
- no hard failures
- no advisory warnings

## Approval Gate

The required approval record now has an explicit state, but not the required
acknowledgments.

- Engineering acknowledgment: `pending explicit named owner`
- Runtime/performance acknowledgment: `pending explicit named owner`
- QA acknowledgment: `pending explicit named owner`
- Guarded residual risks:
  - total shipped JS remains close to the hard cap
  - CTS-GIS SAMRAS/datum umbrella closure still depends on owner acknowledgment

## Task Disposition

- `TASK-PERF-002`: closure evidence satisfied
- `TASK-PERF-003`: closure evidence satisfied
- `TASK-PERF-004`: blocked pending explicit named acknowledgments
- `TASK-PERF-001`: blocked pending `TASK-PERF-004`

## Validation

- `./scripts/benchmarks/build_weight.sh`
- `./scripts/benchmarks/runtime_interactions.sh`
- `python3 scripts/benchmarks/projection_serialization.py`
- `python3 scripts/benchmarks/test_tooling_overhead.py`
- `python3 scripts/benchmarks/check_optimization_budgets.py`
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
- `python3 -m unittest MyCiteV2.tests.integration.test_portal_host_one_shell`
- `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment`
