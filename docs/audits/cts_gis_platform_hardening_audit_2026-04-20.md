# CTS-GIS Platform Hardening Audit

Date: `2026-04-20`

## Scope

This audit reviewed the active CTS-GIS platform path across:

- runtime composition: `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
- service semantics: `MyCiteV2/packages/modules/cross_domain/cts_gis/service.py`
- contract language: `docs/contracts/cts_gis_samras_addressing.md`
- regression coverage: `MyCiteV2/tests/unit/*cts_gis*`, `MyCiteV2/tests/architecture/*portal*`

The goal was to harden the canonical `CTS-GIS` / `cts_gis` / `cts-gis` path, reduce duplicated semantics, and remove contract-unsupported legacy code before any broader Summit data-repair pass.

## Responsibility Map

- `portal_cts_gis_runtime.py`
  - owns request normalization, shell-request generation, source-evidence packaging, and interface-body transport
  - owns `navigation_canvas.mode = "directory_dropdowns"` projection only
- `packages/modules/cross_domain/cts_gis/service.py`
  - owns canonical attention/intention normalization
  - owns render-set derivation for `self`, `children`, `descendants_depth_1_or_2`, and `branch:*`
  - owns geometry projection selection and reference-geometry fallback
- `packages/modules/cross_domain/cts_gis/contracts.py`
  - now owns shared CTS-GIS contract constants and intention-token helpers used by both runtime and service
- `docs/contracts/cts_gis_samras_addressing.md`
  - remains the behavior contract for selection normalization and Garland coupling

## Findings

### Duplicated semantics

- The runtime and service both carried CTS-GIS intention-token normalization.
- The runtime was pre-deciding `self` for selection-only requests even though the service already canonicalizes that behavior.
- Shared CTS-GIS constants existed in multiple files with parallel definitions.

### Dead or contract-unsupported code

- The runtime still carried undocumented navigation branches:
  - `staged_diktataograph`
  - `ordered_hierarchy`
  - `legacy_branch_canvas`
- Those branches were not part of the current public contract, and the live renderer already treated non-`directory_dropdowns` modes as unsupported.

### Summit rendering risk

- The widened Summit County render can be poisoned by a small set of malformed descendant HOPS geometries.
- When those outlier features are included in a shared collection, Garland bounds collapse to a misleading continental-scale extent even though the county shell and many descendants are otherwise valid.
- The service already had reference GeoJSON available for some of these documents, but it only used the reference when HOPS geometry was entirely absent.

## Changes Applied

- Added `packages/modules/cross_domain/cts_gis/contracts.py` to centralize CTS-GIS contract constants and intention-token helpers.
- Refactored the runtime and service to use the shared CTS-GIS contract helpers instead of maintaining parallel intention logic.
- Tightened the runtime boundary so selection-only requests no longer force an intention token into the service call. The service now remains the source of truth for default intention normalization.
- Removed contract-unsupported runtime navigation branches and related dead helpers so the active CTS-GIS path exposes only `directory_dropdowns`.
- Hardened service projection behavior so reference GeoJSON is preferred when HOPS/reference parity warnings prove that the projected HOPS chain has drifted from the authoritative reference geometry.
- Updated the CTS-GIS contract doc to record the service-owned intention default and the reference-geometry fallback rule.

## Remaining Backlog

- Repair the flagged Summit source documents so HOPS and reference geometry converge again and Garland can return to pure `hops` projection for those profiles.
- Extend glossary and contract scans if more CTS-GIS naming drift appears outside the active runtime/service path.
- Consider a dedicated runtime integration test against the live state dataset once the state corpus is stable enough for CI.
