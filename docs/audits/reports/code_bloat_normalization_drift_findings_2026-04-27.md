# Normalization Drift Findings

Date: 2026-04-27

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-27`

## Planning Registry

- Stream ID: `STREAM-CODE-BLOAT-FINDINGS-EXECUTION`
- Compatibility initiative ID: `INIT-CODE-BLOAT-FINDINGS-EXECUTION`
- Findings task: `TASK-CODE-BLOAT-FINDINGS-005`
- Downstream remediation task: `TASK-CODE-BLOAT-REMEDIATION-006`

## Purpose

Record the duplicated runtime normalization surfaces that were consolidated under
the canonical shell/state-machine contract boundary.

## Canonical Helper Ownership

Canonical ownership surface:

- `MyCiteV2/packages/state_machine/portal_shell/shell.py`

Canonical helpers:

- `normalize_runtime_surface_request_payload`
- `normalize_runtime_surface_action_request_payload`
- `normalize_runtime_shell_surface_request_payload`
- `normalize_runtime_shell_action_request_payload`

## Consolidated Drift Inventory

| Drift area | Previous duplication pattern | Canonical owner now used |
| --- | --- | --- |
| Runtime-owned surface requests | Repeated portal-scope + schema + surface-query shaping in tool runtimes | `normalize_runtime_surface_request_payload` |
| Runtime-owned surface actions | Repeated action-kind / action-payload envelope shaping | `normalize_runtime_surface_action_request_payload` |
| Shell-attached tool requests | Repeated shell-state + schema + tool-state shaping | `normalize_runtime_shell_surface_request_payload` |
| Shell-attached tool actions | Repeated shell-state + tool-state + action extraction | `normalize_runtime_shell_action_request_payload` |

Updated call sites:

- `portal_aws_runtime.py`
- `portal_workbench_ui_runtime.py`
- `portal_fnd_dcm_runtime.py`
- `portal_fnd_ebi_runtime.py`
- `portal_cts_gis_runtime.py`

## Parity Evidence

Equivalence coverage now lives in:

- `MyCiteV2/tests/unit/test_portal_runtime_normalization.py`

Covered parity scenarios:

- legacy AWS surface-query aliases remain stable
- envelope-derived AWS action extraction remains stable
- workbench query alias handling remains stable
- FND DCM default capability behavior remains stable
- FND EBI shell-state preservation remains stable
- CTS-GIS tool-state and action payload preservation remain stable

Additional closure-critical regression coverage:

- `MyCiteV2/tests/integration/test_nimm_mutation_contract_flow.py`
- `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`

## Decision

- `TASK-CODE-BLOAT-FINDINGS-005`: `done`
- `TASK-CODE-BLOAT-REMEDIATION-006`: closure evidence satisfied

Why remediation closure is justified:

- duplicated helper ownership is now explicit and canonical
- legacy compatibility behavior is covered by equivalence-style fixtures
- no route widening or authorization drift was introduced by the consolidation

## Validation

- `python3 -m unittest MyCiteV2.tests.unit.test_portal_runtime_normalization`
- `python3 -m unittest MyCiteV2.tests.integration.test_nimm_mutation_contract_flow`
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`

