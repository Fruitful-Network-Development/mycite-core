# Code Bloat Remediation Execution Report

Date: 2026-04-25

Doc type: `execution-report`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-25`

## Planning Registry

- Stream ID: `STREAM-CODE-BLOAT-REMEDIATION`
- Compatibility initiative ID: `INIT-CODE-BLOAT-REMEDIATION`
- Canonical plan:
  `docs/plans/code_bloat_remediation_execution_plan_2026-04-25.md`
- Upstream diagnosis:
  `docs/audits/reports/code_bloat_diagnosis.md`

## Task Evidence Ledger

Remediation status is mixed: `TASK-CODE-BLOAT-REMEDIATION-004` is `done` with
measured latency evidence, while the remaining tasks stay `blocked` on audit
findings dependencies.

| Task ID | Status | Scope | Evidence anchor |
| --- | --- | --- | --- |
| `TASK-CODE-BLOAT-REMEDIATION-001` | blocked | Shell and renderer branch retirement | Awaiting executed shell-topology audit findings (`TASK-CODE-BLOAT-AUDIT-001` produced plan only). |
| `TASK-CODE-BLOAT-REMEDIATION-002` | blocked | Filesystem/bootstrap and snapshot bloat trim | Awaiting executed legacy filesystem/snapshot audit findings (`TASK-CODE-BLOAT-AUDIT-002` produced plan only). |
| `TASK-CODE-BLOAT-REMEDIATION-003` | blocked | Python import and modularity improvements | Awaiting executed Python import/modularity audit findings (`TASK-CODE-BLOAT-AUDIT-003` produced plan only). |
| `TASK-CODE-BLOAT-REMEDIATION-004` | done | Data I/O sizing, caching, and stream boundaries | Runtime cache + prewarm implemented in `portal_system_workspace_runtime.py` / `portal_host/app.py`; latency evidence published in `benchmarks/results/portal_shell_latency_hotfix_2026-04-25.json` and live endpoint timings in `benchmarks/results/portal_shell_live_latency_2026-04-25.json`; cache invalidation regression test added. |
| `TASK-CODE-BLOAT-REMEDIATION-005` | blocked | Frontend bundle decomposition and budget controls | Awaiting executed frontend bundle audit findings (`TASK-CODE-BLOAT-AUDIT-005` produced plan only). |
| `TASK-CODE-BLOAT-REMEDIATION-006` | blocked | Normalization helper consolidation | Awaiting executed normalization-drift audit findings (`TASK-CODE-BLOAT-AUDIT-006` produced plan only). |
| `TASK-CODE-BLOAT-REMEDIATION-007` | blocked | Test/tooling bloat-regression guardrails | Awaiting executed test/tooling overhead audit findings (`TASK-CODE-BLOAT-AUDIT-007` produced plan only). |
| `TASK-CODE-BLOAT-REMEDIATION-008` | blocked | Stream closure publication and sync | Transitively blocked on `TASK-CODE-BLOAT-REMEDIATION-001..007`. |

## Blocker Registry

- `BLOCKER-CODE-BLOAT-AUDIT-FINDINGS-001`
  - Scope: blocks `TASK-CODE-BLOAT-REMEDIATION-001/002/003/005/006/007`.
  - Cause: the upstream `STREAM-CODE-BLOAT-DEEP-AUDIT` closed with audit *plans*
    (`TASK-CODE-BLOAT-AUDIT-001..007`) but no executed audits and no findings
    reports. Remediation acceptance criteria explicitly require audit-derived
    evidence (active/historical shell classification, authority proof for
    filesystem/snapshot adapters, measured import-time hotspots, payload sizing
    and route timings, asset weights, contract-linked helper inventory with
    equivalence fixtures, baseline test/import overhead measurements).
  - Unblock condition: execute the seven planned audits and publish findings
    reports under `docs/audits/reports/` that link back to their respective
    `TASK-CODE-BLOAT-AUDIT-00x` IDs and the parent stream
    `STREAM-CODE-BLOAT-DEEP-AUDIT`. The corrective scope on this report should
    not be mutated speculatively before that evidence exists.
- `BLOCKER-CODE-BLOAT-REMEDIATION-DEPENDENCIES-001`
  - Scope: blocks `TASK-CODE-BLOAT-REMEDIATION-008`.
  - Cause: closure aggregation cannot proceed until upstream remediation tasks
    have results to aggregate.
  - Unblock condition: `TASK-CODE-BLOAT-REMEDIATION-001..007` reach `done`
    state.


- 2026-04-25: Code deploy attempted with `deploy_portal_update.sh --instance fnd --code`; service restart exposed operational dependency drift (`ModuleNotFoundError: yaml` in the portal venv).
- 2026-04-25: Remediated dependency drift by installing `PyYAML` in `/srv/venvs/fnd_portal` and hardening `MyCiteV2/packages/modules/cross_domain/cts_gis/mutation_service.py` so JSON stage input remains available even if YAML dependency is absent; YAML input now fails with explicit `yaml_dependency_missing` mutation error instead of crashing host boot.
- 2026-04-25: Live endpoint confirmation after deployment: `http://127.0.0.1:6101/portal/api/v2/shell` median ~30ms, p95 ~34ms over 8 requests (`benchmarks/results/portal_shell_live_latency_2026-04-25.json`).

## Initial Findings-to-Task Mapping

- Diagnosis area 1 (multi-shell complexity) maps to
  `TASK-CODE-BLOAT-REMEDIATION-001`.
- Diagnosis area 2 (legacy filesystem/snapshots) maps to
  `TASK-CODE-BLOAT-REMEDIATION-002`.
- Diagnosis area 3 (import bloat/monolith modules) maps to
  `TASK-CODE-BLOAT-REMEDIATION-003`.
- Diagnosis areas 4 and 6 (I/O and caching) map to
  `TASK-CODE-BLOAT-REMEDIATION-004`.
- Diagnosis area 5 (frontend bundles) maps to
  `TASK-CODE-BLOAT-REMEDIATION-005`.
- Diagnosis area 7 (normalization drift) maps to
  `TASK-CODE-BLOAT-REMEDIATION-006`.
- Diagnosis area 8 (testing/tooling overhead) maps to
  `TASK-CODE-BLOAT-REMEDIATION-007`.

## Validation Log

- 2026-04-25: Remediation triage initially transitioned all eight remediation
  tasks `pending` -> `blocked` pending executed deep-audit findings.
- 2026-04-25: User-reported portal-open latency investigated with runtime
  profiling; root cause identified in repeated system workbench projection and
  datum-recognition rebuild on each shell request.
- 2026-04-25: Implemented deterministic workbench-projection cache keyed by
  authority-db path + mtime in
  `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`, plus
  startup prewarm in `MyCiteV2/instances/_shared/portal_host/app.py`.
- 2026-04-25: Published evidence in
  `benchmarks/results/portal_shell_latency_hotfix_2026-04-25.json`:
  baseline shell latency median ~5294ms (p95 ~6967ms) before fix; prewarmed
  shell request ~22ms and warm median ~19.8ms after fix.
- 2026-04-25: Added cache invalidation regression test
  `test_system_workbench_projection_uses_cache_until_authority_mtime_changes` in
  `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`.
- Remaining closure is gated by unresolved deep-audit-dependent tasks
  (`TASK-CODE-BLOAT-REMEDIATION-001/002/003/005/006/007`) and transitive
  closure dependency `TASK-CODE-BLOAT-REMEDIATION-008`.
