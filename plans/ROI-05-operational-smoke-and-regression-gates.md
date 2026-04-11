# ROI 05 — Operational Smoke Checks and Regression Gates

## Objective

Promote current portal smoke checks into a standard regression gate so future portal changes cannot silently reintroduce stale-build or missing-static regressions.

## Why this is high ROI

The repo already has useful integration and architecture tests, including shell-template/static delivery checks and no-fallback-nav boundaries. Those are valuable, but they still stop at repo behavior.

This area yields high return because it extends that discipline into deployment and release cadence.

## Scope

Primary files and surfaces:

- `MyCiteV2/tests/integration/test_v2_native_portal_host.py`
- `MyCiteV2/tests/architecture/test_v2_native_portal_host_boundaries.py`
- any release or deploy notes for the portal
- any future script added for live smoke verification

## Deliverables

1. A standard smoke command set for portal releases.
2. A documented rule that portal changes are not done until smoke passes.
3. Optional wrapper script for smoke execution.
4. A task/report convention that records smoke output.

## Definition of done

This ROI area is complete when:

- repo tests remain part of the gate
- live smoke checks are also part of the gate
- smoke checks are documented in one stable place
- portal tasks include smoke output in their reports

## Suggested implementation shape

Use a two-layer gate:

### Layer 1 — Repo gate

- integration tests
- architecture tests
- any focused runtime tests

### Layer 2 — Operational smoke gate

- `/portal/system` marker check
- static CSS 200
- static JS 200
- `/healthz` static bundle verification
- optional screenshot/manual visual confirmation when layout matters

## Task classification

`repo_and_deploy`

## Agent execution plan

### Lead

- require both repo gate and smoke gate in the task acceptance criteria
- set status to `verification_pending` after implementation is complete

### Implementer

- run repo tests
- perform deployment or deploy handoff
- record smoke commands if deploy access exists
- otherwise stop at `deploy not performed`

### Verifier

- rerun the smoke gate independently
- treat smoke failure as task failure
- verify that repo tests and live smoke both passed

## Required evidence pattern

- repo test command and result
- live smoke command and result
- final pass/fail based on both layers
