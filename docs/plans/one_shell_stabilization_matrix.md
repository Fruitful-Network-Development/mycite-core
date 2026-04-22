# One-Shell Stabilization Matrix

Date: 2026-04-21

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-21`

## Purpose

Define the shell-boundary route matrix used to prevent refactor drift.

Canonical owner contracts:

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/tool_operating_contract.md`

## Matrix Columns

Each route must assert:

- canonical URL/query projection
- state owner (`reducer-owned` or `runtime-owned`)
- first-load visible regions
- expected region payload family
- allowed directive action posture

## Required Routes

### `/portal/system`

- state owner: `reducer-owned`
- first-load visible: `control_panel`, `workbench`
- first-load collapsed: `interface_panel`
- region family mapping:
  - workbench: `reflective_workspace`
  - control panel: `directive_panel`
  - interface panel: `presentation_surface` (collapsed until mediation subject/open state)

### `/portal/system/tools/aws-csm`

- state owner: `runtime-owned`
- first-load visible: `control_panel`, `interface_panel`
- first-load collapsed: `workbench`
- region family mapping:
  - workbench: `reflective_workspace` (secondary evidence only)
  - control panel: `directive_panel`
  - interface panel: `presentation_surface`

### `/portal/system/tools/cts-gis`

- state owner: `runtime-owned`
- first-load visible: `control_panel`, `interface_panel`
- first-load collapsed: `workbench`
- region family mapping:
  - workbench: `reflective_workspace` (secondary evidence only)
  - control panel: `directive_panel`
  - interface panel: `presentation_surface`

### `/portal/system/tools/fnd-dcm`

- state owner: `runtime-owned`
- first-load visible: `control_panel`, `interface_panel`
- first-load collapsed: `workbench`
- region family mapping:
  - workbench: `reflective_workspace` (secondary evidence only)
  - control panel: `directive_panel`
  - interface panel: `presentation_surface`

### `/portal/system/tools/workbench-ui`

- state owner: `runtime-owned`
- first-load visible: `control_panel`, `workbench`, `interface_panel`
- first-load collapsed: none
- region family mapping:
  - workbench: `reflective_workspace` (primary)
  - control panel: `directive_panel`
  - interface panel: `presentation_surface`

### `/portal/network`

- state owner: `runtime-owned`
- first-load visible: `control_panel`, `workbench`
- first-load collapsed: `interface_panel` until selected record
- region family mapping:
  - workbench: `reflective_workspace`
  - control panel: `directive_panel`
  - interface panel: `presentation_surface`

### `/portal/utilities`

- state owner: `runtime-owned`
- first-load visible: `control_panel`, `workbench`
- first-load collapsed: `interface_panel` unless section projects detail
- region family mapping:
  - workbench: `reflective_workspace`
  - control panel: `directive_panel`
  - interface panel: `presentation_surface`

## Test Ownership

- route and composition behavior: `MyCiteV2/tests/unit/test_portal_shell_contract.py`
- shell/static boundary guards: `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
- docs/contract alignment and matrix presence: `MyCiteV2/tests/contracts/test_contract_docs_alignment.py`
- matrix contract gate: `MyCiteV2/tests/architecture/test_portal_shell_stabilization_matrix.py`
