# Code Bloat Remediation Execution Report

Date: 2026-04-25

Doc type: `execution-report`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-27`

## Planning Registry

- Stream ID: `STREAM-CODE-BLOAT-REMEDIATION`
- Compatibility initiative ID: `INIT-CODE-BLOAT-REMEDIATION`
- Canonical plan:
  `docs/plans/code_bloat_remediation_execution_plan_2026-04-25.md`
- Upstream diagnosis:
  `docs/audits/reports/code_bloat_diagnosis.md`

## Task Evidence Ledger

| Task ID | Status | Scope | Evidence anchor |
| --- | --- | --- | --- |
| `TASK-CODE-BLOAT-REMEDIATION-001` | done | Retire residual multi-shell and renderer branch pathways | `docs/audits/reports/code_bloat_shell_topology_findings_2026-04-25.md` |
| `TASK-CODE-BLOAT-REMEDIATION-002` | done | Retire legacy filesystem datum/bootstrap paths and snapshot bloat | `docs/audits/reports/code_bloat_legacy_filesystem_snapshot_findings_2026-04-25.md` |
| `TASK-CODE-BLOAT-REMEDIATION-003` | done | Reduce Python import graph bloat and modularize monolith runtime surfaces | `docs/audits/reports/code_bloat_python_import_modularity_findings_2026-04-25.md` |
| `TASK-CODE-BLOAT-REMEDIATION-004` | done | Implement data I/O sizing controls and cache/stream boundaries | `benchmarks/results/portal_shell_latency_hotfix_2026-04-25.json` |
| `TASK-CODE-BLOAT-REMEDIATION-005` | done | Decompose frontend bundles and enforce asset budget controls | `docs/audits/reports/code_bloat_frontend_bundle_findings_2026-04-27.md` |
| `TASK-CODE-BLOAT-REMEDIATION-006` | done | Consolidate duplicated normalization helpers under canonical contracts | `docs/audits/reports/code_bloat_normalization_drift_findings_2026-04-27.md` |
| `TASK-CODE-BLOAT-REMEDIATION-007` | done | Add bloat-regression guardrails for tests, linting, and CI budgets | `docs/audits/reports/code_bloat_test_tooling_overhead_findings_2026-04-27.md` |
| `TASK-CODE-BLOAT-REMEDIATION-008` | done | Publish remediation execution evidence and close corrective stream | this report + synchronized manifests/task boards |

## 2026-04-27 Closure Outcomes

### Frontend bundle decomposition

- The portal stayed on the canonical static-serving/module-registry model.
- CTS-GIS inspector rendering moved behind a deferred shell module without
  adding a bundler or a second stack.
- `initial_load_gzip_bytes` now measures `35,488 B`, under the hard `41,000 B`
  budget.

### Normalization consolidation

- Canonical normalization now lives in `portal_shell/shell.py`.
- Runtime-owned and shell-attached tool surfaces now reuse the same helper
  family instead of each runtime carrying slightly different schema/scope logic.
- Equivalence coverage is recorded in
  `MyCiteV2/tests/unit/test_portal_runtime_normalization.py`.

### Guardrails

- Machine-readable budgets now cover asset size, interaction latency,
  projection CPU, and import overhead.
- `scripts/benchmarks/check_optimization_budgets.py` currently returns
  `status=pass`.
- Closure-critical architecture, integration, contract, and unit suites remain
  green after the guardrail additions.

## Residual Risk

- The performance approval gate remains separate work under `TASK-PERF-004`;
  this remediation stream does not treat missing human acknowledgment as a
  blocker for code-bloat corrective closure.
- Total shipped JS is intentionally close to the hard cap (`64,781 / 65,000`),
  so future growth will surface immediately in the budget check.

## Lifecycle Decision

- `TASK-CODE-BLOAT-REMEDIATION-008`: closed
- `STREAM-CODE-BLOAT-REMEDIATION`: closure evidence complete
- `STREAM-CODE-BLOAT-FINDINGS-EXECUTION`: closure evidence complete

Historical notes from earlier remediation passes remain preserved in the linked
supporting reports and benchmark artifacts.

## Validation Log

- `./scripts/benchmarks/build_weight.sh`
- `python3 scripts/benchmarks/test_tooling_overhead.py`
- `python3 scripts/benchmarks/check_optimization_budgets.py`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_runtime_normalization`
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
- `python3 -m unittest MyCiteV2.tests.integration.test_portal_host_one_shell`
- `python3 -m unittest MyCiteV2.tests.integration.test_nimm_mutation_contract_flow`
- `git diff --check`
