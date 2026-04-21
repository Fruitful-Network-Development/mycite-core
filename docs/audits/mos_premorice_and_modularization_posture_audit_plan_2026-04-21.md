# MOS Premorice and Modularization Posture Audit Plan

Date: 2026-04-21

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-21`

## Purpose

Audit MOS post-cutover posture for premorice (state-memory continuity and
predictable carry-forward context) and modularization boundaries across shell,
tool runtimes, and adapters.

## Scope

- `MyCiteV2/packages/state_machine/portal_shell/shell.py`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
- `MyCiteV2/packages/ports/**`
- `MyCiteV2/packages/adapters/**`

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/route_model.md`
- `docs/contracts/portal_vocabulary_glossary.md`

## Workstreams

### 1) Premorice continuity checks

- shell-state continuity across reducer-owned vs runtime-owned surfaces
- focus-path canonicalization and back-out behavior
- tool-local state carry without widening shared shell schema

### 2) Modular boundary checks

- port-first access between runtime and persistence layers
- adapter containment and no runtime reach-through into private internals
- shared helper reuse vs repeated local forks

### 3) Performance-sensitive boundary checks

- repeated payload-building hotspots
- repeated authority reads per request
- diagnostics parity across surfaces for drift detection

## Exit Criteria

- Published drift matrix for premorice and modular boundaries.
- Critical boundary violations have concrete owner and patch path.
- Ongoing diagnostics/test hooks are named for regression prevention.
