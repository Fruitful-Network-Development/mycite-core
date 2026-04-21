# MOS Database Authority and Peripheral Access Audit Plan

Date: 2026-04-21

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-21`

## Purpose

Audit the end-to-end MOS authority path: database truth, package-peripheral
operation, tool exposure, and FND authorization boundaries. Confirm that access
is granted through explicit authority posture rather than implicit defaults.

## Scope

Authority data:

- `deployed/fnd/private/mos_authority.sqlite3`

Host/runtime:

- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`

Ports/adapters:

- `MyCiteV2/packages/ports/portal_authority/contracts.py`
- `MyCiteV2/packages/adapters/sql/portal_authority.py`
- `MyCiteV2/packages/adapters/sql/datum_store.py`

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`

## Investigation Tracks

### 1) Database authority reality

Validate table population, tenant scoping, and expected corpus shape for
documents, rows, workbench snapshots, publication snapshots, and authority
snapshots.

### 2) Peripheral/package grant model

Trace how portal authority data becomes runtime capabilities and tool exposure,
including fallback posture when authority records are missing.

### 3) Tool access mediation

Verify how tools are exposed/enabled/operationalized and where missing
capabilities or integrations prevent operation.

### 4) FND privileged posture

Confirm current FND capability set and its relation to privileged tool routes
(`fnd_dcm`, `fnd_ebi`) without widening non-FND assumptions.

## Verification Commands

- SQL count queries for authority tables and CTS-GIS subset counts.
- unit tests touching SQL authority and shell/runtime composition.
- runtime payload spot checks for `tool_rows`, `readiness`, and envelope errors.

## Exit Criteria

- Published report maps DB truth -> runtime grants -> tool access -> UI posture.
- Any implicit/default grant behavior is flagged with severity.
- FND privileged posture is explicitly documented as contract-backed behavior.
