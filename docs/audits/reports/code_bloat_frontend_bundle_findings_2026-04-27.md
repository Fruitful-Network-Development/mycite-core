# Frontend Bundle Findings

Date: 2026-04-27

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-27`

## Planning Registry

- Stream ID: `STREAM-CODE-BLOAT-FINDINGS-EXECUTION`
- Compatibility initiative ID: `INIT-CODE-BLOAT-FINDINGS-EXECUTION`
- Findings task: `TASK-CODE-BLOAT-FINDINGS-004`
- Downstream remediation task: `TASK-CODE-BLOAT-REMEDIATION-005`

## Purpose

Publish executed frontend bundle findings for the one-shell portal without
introducing a second frontend stack or a new bundler.

## Canonical Implementation Surface

- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_host.js`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js`
- `benchmarks/results/build_weight_baseline.json`
- `benchmarks/results/portal_healthz_probe_2026-04-27.json`

## Findings

### 1) The canonical loading model is still static-serving plus module-registry loading

No bundler or second frontend stack was introduced.

- `app.py` remains the canonical asset manifest authority.
- `v2_portal_shell.js` remains the canonical shell module loader.
- Deferred modules now load through `window.__MYCITE_V2_LOAD_SHELL_MODULE(...)`
  while preserving the existing self-registration contract.

### 2) Startup-critical versus deferred ownership is now explicit and route-scoped

Startup-critical modules:

- `region_renderers`
- `tool_surface_adapter`
- `workbench_renderers`
- `inspector_renderers`
- `shell_core`
- `shell_watchdog`

Deferred modules:

- `aws_workspace`
- `system_workspace`
- `network_workspace`
- `cts_gis_surface`

Deferred classification is evidence-backed rather than aspirational:

- workspace renderers load only when their reflective workspace surface is
  requested
- the CTS-GIS inspector now uses a small startup host
  (`v2_portal_inspector_host.js`) that lazily loads the heavier Garland /
  Diktataograph renderer (`v2_portal_inspector_renderers.js`) only when the
  CTS-GIS presentation surface is active

### 3) Measured initial-load posture improved materially on FND-first evidence

| Metric | Historical baseline | 2026-04-27 measured | Delta |
| --- | ---: | ---: | ---: |
| Initial JS raw bytes | `221,798` | `167,500` | `-24.5%` |
| Initial JS gzip bytes | `45,606` | `35,488` | `-22.2%` |
| Total JS gzip bytes | `narrative-only prior; no canonical hard gate` | `64,781` | `tracked under hard cap 65,000` |
| Deferred JS gzip bytes | `not separately budgeted previously` | `29,293` | `new advisory metric` |

Measured from:

- `benchmarks/results/build_weight_baseline.json`
- `benchmarks/results/optimization_budget_check.json`

Current hard-budget result:

- `initial_load_gzip_bytes`: pass (`35,488 <= 41,000`)
- `total_gzip_bytes`: pass (`64,781 <= 65,000`)

### 4) Route-level lazy loading is evidenced without breaking shell contracts

Implemented route-level behavior:

- reflective workspace hosts defer workspace renderer modules
- presentation surface hosts defer CTS-GIS inspector rendering
- cache/version posture remains query-versioned static assets through the
  manifest `cache_policy`

Relevant evidence:

- `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
- `MyCiteV2/tests/integration/test_portal_host_one_shell.py`
- `benchmarks/results/portal_healthz_probe_2026-04-27.json`

### 5) Residual risk is now bounded rather than ambiguous

- Total shipped JS remains close to the new hard cap (`64,781 / 65,000`), so
  future module creep is intentionally constrained by the budget gate.
- The deferred CTS-GIS split prioritizes first-load performance first; shared
  helper de-duplication remains a future optimization, not a hidden regression.

## Decision

- `TASK-CODE-BLOAT-FINDINGS-004`: `done`
- `TASK-CODE-BLOAT-REMEDIATION-005`: closure evidence satisfied

Why remediation closure is justified:

- asset ownership is now decomposed by startup-critical vs deferred routes
- invalidation and compression posture are documented in the canonical manifest
- measured first-load weight improved materially on FND-first evidence
- no second frontend stack or bundler was introduced

## Validation

- `./scripts/benchmarks/build_weight.sh`
- `python3 scripts/benchmarks/check_optimization_budgets.py`
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
- `python3 -m unittest MyCiteV2.tests.integration.test_portal_host_one_shell`

