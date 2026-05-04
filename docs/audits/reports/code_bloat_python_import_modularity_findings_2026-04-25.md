# Code Bloat Python Import + Modularity Findings

Date: 2026-04-25

Doc type: `audit-report`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-25`

## Registry

- Stream ID: `STREAM-CODE-BLOAT-FINDINGS-EXECUTION`
- Compatibility initiative ID: `INIT-CODE-BLOAT-FINDINGS-EXECUTION`
- Findings task ID: `TASK-CODE-BLOAT-FINDINGS-003`
- Upstream planning task ID: `TASK-CODE-BLOAT-AUDIT-003`
- Downstream remediation task ID: `TASK-CODE-BLOAT-REMEDIATION-003`
- Source audit plan:
  `docs/audits/code_bloat_python_import_modularity_audit_plan_2026-04-24.md`

## Scope

Measure import-time startup pressure for portal host/runtime surfaces and classify
safe deferral candidates versus contract-required eager imports.

## Import-Time Baseline (Before Refactor)

Measured with:

- `python3 -X importtime -c "import MyCiteV2.instances._shared.portal_host.app"`
- `python3 -X importtime -c "import MyCiteV2.instances._shared.runtime.portal_shell_runtime"`

Observed totals:

- `portal_host.app`: ~230,203us
- `portal_shell_runtime`: ~224,678us

Top self-time contributors included:

- `MyCiteV2.packages.state_machine.portal_shell.shell`
- `MyCiteV2.packages.ports.datum_store.contracts`
- `yaml.reader`
- `MyCiteV2.packages.modules.cross_domain.local_audit.service`

## Findings Classification

### 1) Safe deferral candidates (executed)

`MyCiteV2/instances/_shared/portal_host/app.py`

- Tool runtime imports were eagerly loaded at module import time even though most
  are only used by route handlers.
- Classification: `safe_to_defer`
- Executed remediation:
  - lazy import tool runtime functions inside route handlers for AWS-CSM,
    CTS-GIS, FND-DCM, FND-EBI, and Workbench-UI.
  - lazy import `NimmDirectiveEnvelope` only in mutation parsing helpers.
  - lazy import system-workbench warmup dependency in warmup function.

`MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`

- Tool bundle builders imported all tool runtimes eagerly.
- Mutation/network-only paths imported additional heavy modules eagerly.
- Classification: `safe_to_defer`
- Executed remediation:
  - lazy import tool-specific bundle builders inside each tool-builder function.
  - lazy import network filesystem adapter/service in network payload path.
  - lazy import publication and local-audit services in profile-basics mutation path.

### 2) Contract-required eager imports (retained)

- Core shell contract and runtime-platform imports remain eager in
  `portal_shell_runtime.py` because they define canonical request normalization,
  route ownership, and envelope composition invariants.
- SQL adapter imports used across multiple hot paths remain eager for readability
  and deterministic behavior.

Classification: `required_eager`.

## Modularization Disposition

No risky module split was required to close this cycle. Import pressure reduction
was achieved first through safe deferral at adapter/runtime boundaries while
preserving one-shell contract behavior.

## Regression/Verification

Validation commands executed for this findings/remediation cycle:

- `python3 -m unittest MyCiteV2.tests.unit.test_portal_shell_sql_authority`
- `python3 -m unittest MyCiteV2.tests.integration.test_portal_host_one_shell`
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`

All returned successful exit status in this execution environment.

## Remediation Disposition

`TASK-CODE-BLOAT-REMEDIATION-003` can close on evidence: import-time hotspots
were identified, safe lazy-import deferrals were applied to `portal_host.app`
and `portal_shell_runtime`, import-side effects were reduced for non-hot-path
surfaces, and regressions passed for shell authority, one-shell integration, and
architecture boundaries.
