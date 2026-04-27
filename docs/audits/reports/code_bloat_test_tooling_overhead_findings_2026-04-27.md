# Test And Tooling Overhead Findings

Date: 2026-04-27

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-27`

## Planning Registry

- Stream ID: `STREAM-CODE-BLOAT-FINDINGS-EXECUTION`
- Compatibility initiative ID: `INIT-CODE-BLOAT-FINDINGS-EXECUTION`
- Findings task: `TASK-CODE-BLOAT-FINDINGS-006`
- Downstream remediation task: `TASK-CODE-BLOAT-REMEDIATION-007`
- Shared performance dependency: `TASK-PERF-003`

## Purpose

Publish measured test/tooling overhead findings and distinguish hard guardrail
metrics from advisory-only maintenance signals.

## Measured Overhead

Source artifacts:

- `benchmarks/results/test_tooling_overhead_baseline.json`
- `benchmarks/results/optimization_budget_check.json`
- `benchmarks/budgets/optimization_budgets.json`

Measured values:

| Metric | Measured | Budget | Enforcement | Result |
| --- | ---: | ---: | --- | --- |
| Aggregate import median | `345.838 ms` baseline, `384.0 ms` rerun | `400.0 ms` | `advisory` | pass |
| Aggregate import p95 | `503.059 ms` baseline, `632.918 ms` rerun | `650.0 ms` | `advisory` | pass |
| Repeated private helper name count | `14` | `14` | `advisory` | pass |
| Test file count | `97` | tracked only | advisory context | n/a |

Representative sampled imports:

- `portal_shell_runtime`: median `272.9 ms`, p95 `394.59 ms`
- `portal_cts_gis_runtime`: median `377.221 ms`, p95 `413.295 ms`
- `test_portal_workspace_runtime_behavior`: median `487.339 ms`, p95 `503.059 ms`

## Hard vs Advisory Guardrails

Hard-threshold-ready now:

- initial asset weight
- interaction latency
- projection CPU

Advisory-only for this cycle:

- aggregate import median / p95 because reruns still show meaningful variance
- repeated helper duplication count
- total test-file count without deeper suite partitioning work

Rationale:

- measured runtime/import budgets were stable enough to enforce
- helper duplication still needs follow-on consolidation work to reduce noise

## Decision

- `TASK-CODE-BLOAT-FINDINGS-006`: `done`
- `TASK-CODE-BLOAT-REMEDIATION-007`: closure evidence satisfied

Why remediation closure is justified:

- repo now contains machine-readable optimization budgets
- the guardrail script runs successfully and returns `status=pass`
- import-overhead thresholds are explicitly staged as advisory rather than
  falsely hardened while the measurement remains noisy
- closure-critical architecture, integration, contract, and unit suites remained
  green after the guardrail addition

## Validation

- `python3 scripts/benchmarks/test_tooling_overhead.py`
- `python3 scripts/benchmarks/check_optimization_budgets.py`
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
- `python3 -m unittest MyCiteV2.tests.integration.test_portal_host_one_shell`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_workspace_runtime_behavior`
- `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment`
