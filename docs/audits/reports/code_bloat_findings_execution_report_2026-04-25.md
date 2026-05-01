# Code Bloat Findings Execution Report

Date: 2026-04-25

Doc type: `execution-report`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-27`

## Planning Registry

- Stream ID: `STREAM-CODE-BLOAT-FINDINGS-EXECUTION`
- Compatibility initiative ID: `INIT-CODE-BLOAT-FINDINGS-EXECUTION`
- Canonical plan:
  `docs/plans/code_bloat_findings_execution_plan_2026-04-25.md`
- Upstream planning stream: `STREAM-CODE-BLOAT-DEEP-AUDIT`
- Downstream corrective stream: `STREAM-CODE-BLOAT-REMEDIATION`

## Task Evidence Ledger

| Task ID | Status | Scope | Evidence anchor |
| --- | --- | --- | --- |
| `TASK-CODE-BLOAT-FINDINGS-001` | done | Shell topology and renderer-family findings | `docs/audits/reports/code_bloat_shell_topology_findings_2026-04-25.md` |
| `TASK-CODE-BLOAT-FINDINGS-002` | done | Legacy filesystem adapter + deployed snapshot classification | `docs/audits/reports/code_bloat_legacy_filesystem_snapshot_findings_2026-04-25.md` |
| `TASK-CODE-BLOAT-FINDINGS-003` | done | Python import-time / modularity findings | `docs/audits/reports/code_bloat_python_import_modularity_findings_2026-04-25.md` |
| `TASK-CODE-BLOAT-FINDINGS-004` | done | Frontend bundle decomposition and startup/deferred ownership findings | `docs/audits/reports/code_bloat_frontend_bundle_findings_2026-04-27.md` |
| `TASK-CODE-BLOAT-FINDINGS-005` | done | Normalization drift inventory and canonical helper ownership map | `docs/audits/reports/code_bloat_normalization_drift_findings_2026-04-27.md` |
| `TASK-CODE-BLOAT-FINDINGS-006` | done | Test/tooling overhead findings and hard-vs-advisory guardrail split | `docs/audits/reports/code_bloat_test_tooling_overhead_findings_2026-04-27.md` |

## Findings Stream Status

The executed findings stream is now complete for the active remediation scope.

Closure outcomes:

- shell-topology findings closed `TASK-CODE-BLOAT-REMEDIATION-001`
- filesystem/snapshot findings closed `TASK-CODE-BLOAT-REMEDIATION-002`
- import/modularity findings closed `TASK-CODE-BLOAT-REMEDIATION-003`
- frontend bundle findings closed `TASK-CODE-BLOAT-REMEDIATION-005`
- normalization findings closed `TASK-CODE-BLOAT-REMEDIATION-006`
- test/tooling findings closed `TASK-CODE-BLOAT-REMEDIATION-007`

## Key Measured Outcomes

- Initial shell JS gzip moved to `35,488 B` under the hard `41,000 B` budget
  after explicit deferred-module loading was implemented.
- Canonical runtime normalization now lives in
  `MyCiteV2/packages/state_machine/portal_shell/shell.py` with parity coverage
  in `MyCiteV2/tests/unit/test_portal_runtime_normalization.py`.
- Machine-readable optimization budgets now execute from
  `scripts/benchmarks/check_optimization_budgets.py` and currently return
  `status=pass`.

## Lifecycle Note

This report remains the canonical findings execution ledger for the code-bloat
findings stream. The individual 2026-04-27 findings reports are supporting
evidence, not replacements for this execution summary.

## Validation Log

- `./scripts/benchmarks/build_weight.sh`
- `python3 scripts/benchmarks/test_tooling_overhead.py`
- `python3 scripts/benchmarks/check_optimization_budgets.py`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_runtime_normalization`
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
- `python3 -m unittest MyCiteV2.tests.integration.test_portal_host_one_shell`
- `python3 -m unittest MyCiteV2.tests.integration.test_nimm_mutation_contract_flow`
