# Peripheral Packages Modularization Report

Date: 2026-04-16
Scope: `MyCiteV2/packages/modules/cross_domain/**`
Reference plan: `docs/audits/peripheral_packages_modularization_audit_plan_2026-04-16.md`

## 1) Inventory Matrix (module-by-module)

Legend:
- Risk: `low` (localized transform-only), `medium` (port-heavy but bounded), `high` (multi-port orchestration and implicit contract coupling)
- Contract I/O: primary request/response shapes exposed at module boundary

| Module | Public entrypoints | Inbound dependencies (known callers) | Outbound dependencies | Side effects | Contract I/O | Coupling risk |
|---|---|---|---|---|---|---|
| `aws_csm_newsletter` | `AwsCsmNewsletterService` (+ schema constants via package `__init__`) | script bootstrap + unit tests (no runtime wiring found in current tree) | `ports.aws_csm_newsletter` (`AwsCsmNewsletterStatePort`, `AwsCsmNewsletterCloudPort`) | Secret creation/read, queue dispatch, lambda/receipt health reads, S3 read, persisted profile/contact-log writes via port | Domain-scoped newsletter profile/contact log and dispatch/inbound callbacks | high |
| `aws_csm_onboarding` | `AwsCsmOnboardingService`, `AwsCsmOnboardingUnconfiguredCloudPort` | no direct runtime caller found (currently package-exported, tested indirectly via adapter/port contracts) | `ports.aws_csm_onboarding` + `core.datum_refs` (plus unused import from `ports.aws_read_only_status`) | Profile load/save through profile-store port, cloud patch reads; no direct infra import | `AwsCsmOnboardingCommand -> AwsCsmOnboardingOutcome` | medium |
| `aws_narrow_write` | `AwsNarrowWriteCommand`, `AwsNarrowWriteOutcome`, `normalize_aws_narrow_write_command`, `AwsNarrowWriteService` | unit tests + architecture boundary tests | `ports.aws_narrow_write`, `core.datum_refs`, and cross-domain read model (`aws_operational_visibility`) | Narrow-write apply through port; no direct adapter I/O in module | write request normalization + confirmation envelope projection | medium |
| `aws_operational_visibility` | `normalize_aws_operational_visibility`, `CanonicalNewsletterOperationalProfile`, `AwsReadOnlyOperationalVisibility`, `AwsOperationalVisibilityService` | `aws_narrow_write` + unit/architecture tests | `ports.aws_read_only_status`; local helper policy module | Read-only status fetch via port; no writes | tenant-scope read request -> sanitized canonical read-only profile | medium |
| `cts_gis` | `CtsGisReadOnlyService` | portal runtime (`portal_cts_gis_runtime.py`) + unit tests | `ports.datum_store`, `ports.datum_store.cts_gis_legacy_compat`, `modules.domains.datum_recognition`, `core.structures.hops` | Reads authoritative datum document through port; pure projection assembly in-process | mediation request bundle + map/workbench surface projection payload | high |
| `fnd_ebi` | `FndEbiReadOnlyService` | unit tests (runtime wiring currently via port contracts, not module import in scanned files) | `ports.fnd_ebi_read_only` | Read-only profile fetch via port | tenant/domain/month filters -> hosted analytics dashboard surface payload | low |
| `local_audit` | `LocalAuditService`, normalization/value objects (`LocalAuditRecord`, `StoredLocalAuditRecord`, projections) | portal runtimes (`mvp_runtime`, `portal_shell_runtime`, `portal_system_workspace_runtime`) + tests | `ports.audit_log`, `core.datum_refs` | Append/read recent audit records via audit-log port; catches storage decode/os errors for status projection | local-audit record append/read and operational-status/recent-activity projections | medium |
| `network_root` | `NetworkRootReadModelService` | portal shell runtime | `ports.network_root_read_model` | Read-only model fetch via port | portal tenant/domain/query -> network workspace surface payload | low |
| `external_events` | none (inert scaffold) | none found | none | none | none | low |

## 2) Conformance Checks from Plan Section 2

### A. Directionality (Hexagonal boundaries)

**Pass**
- No direct imports from `packages/adapters/**` were found in `cross_domain` services.
- Infra concerns are largely expressed through explicit ports (`aws_*`, `audit_log`, `datum_store`, `network_root_read_model`, `fnd_ebi_read_only`).

**Findings / flags**
- `aws_narrow_write` depends on `aws_operational_visibility` (cross-module read-before-write guard). This is acceptable but creates cross-module coupling that should be kept one-directional (`write` depending on `read` only) and documented as intentional.
- `aws_csm_onboarding/service.py` imports `AwsReadOnlyStatusRequest` but does not use it. This is harmless but expands apparent dependency surface and should be removed.

### B. API surface

**Pass**
- Most module packages define explicit `__all__` in their package `__init__.py`.
- Boundary normalization exists in key modules (`aws_narrow_write`, `local_audit`, `aws_operational_visibility`, `aws_csm_newsletter`).

**Findings / flags**
- Several service modules themselves do not define local `__all__`; package-level exports are stable, but intra-module explicitness is inconsistent.
- `aws_csm_newsletter` has the broadest public behavior surface under a single service class (domain bootstrap, health, subscribe/unsubscribe, callback processing, queue dispatch orchestration), raising future extraction risk.

### C. Error and observability

**Pass**
- Domain-significant validation errors are explicit (`ValueError`, `LookupError`, `PermissionError`, policy error type for onboarding).
- Sensitive-key rejection is explicit in `local_audit` and `aws_operational_visibility`.

**Findings / flags**
- Error taxonomy is not standardized across modules (mix of built-in exceptions and custom policy errors).
- Limited structured telemetry in cross-domain modules themselves (mostly return payload warnings and exceptions). Observability appears adapter/runtime-driven, not module-standardized.
- `local_audit` intentionally downgrades some storage exceptions to degraded-status outputs, which is good for resilience but should remain contract-verified.

### D. State and side effects

**Pass**
- Most side effects are mediated through ports.
- Transform-heavy logic remains testable and pure in helper functions/dataclasses.

**Findings / flags**
- `aws_csm_newsletter` combines high-volume pure transforms with side-effect orchestration in one service.
- Timestamp/token generation patterns are duplicated (UTC-now helpers + secret/token rendering) across modules and should be centralized where semantics match.

### E. Backward compatibility

**Pass**
- `cts_gis` explicitly carries legacy compatibility via `cts_gis_legacy_compat` port helpers and intention-token fallback logic.
- `local_audit` and `aws_operational_visibility` constrain and normalize outward payloads to stable sets.

**Findings / flags**
- Compatibility behavior appears module-local and ad hoc; there is no shared compatibility layer for common aliasing/legacy-name handling.
- Backward-compatibility policy windows/deprecation markers are not centrally declared in cross-domain modules.

## 3) Repeated Patterns and Extraction Candidates (2+ modules only)

> Candidate rule applied: extraction proposed only where behavior appears in at least two modules with shared semantics.

### Candidate A: Scalar normalization helpers (`_as_text`, dict/list coercion)
- Seen in: `aws_csm_newsletter`, `aws_csm_onboarding`, `aws_narrow_write`, `aws_operational_visibility`, `cts_gis`, `fnd_ebi`, `local_audit`, `network_root`.
- Proposed shared path: `MyCiteV2/packages/modules/shared/scalars.py`
- Proposed exports:
  - `as_text(value: object) -> str`
  - `as_dict(value: Any) -> dict[str, Any]`
  - `as_dict_list(value: object) -> list[dict[str, Any]]`
- Notes: keep strict behavior-compatible wrappers in source modules during transition to avoid drift.

### Candidate B: Datum-reference normalization at boundary
- Seen in: `aws_csm_onboarding`, `aws_narrow_write`, `local_audit`.
- Proposed shared path: `MyCiteV2/packages/modules/shared/datum_boundary.py`
- Proposed exports:
  - `normalize_focus_subject(value: object, *, field_name: str) -> str`
- Notes: thin wrapper around `core.datum_refs.normalize_datum_ref` for consistent field naming and error text.

### Candidate C: Secret/forbidden-key recursive rejection utilities
- Seen in: `aws_operational_visibility` and `local_audit`.
- Proposed shared path: `MyCiteV2/packages/modules/shared/redaction_guards.py`
- Proposed exports:
  - `reject_forbidden_keys(payload: Any, *, forbidden_keys: set[str], field_name: str) -> None`
- Notes: keep module-specific forbidden-key sets local; only recursive walker should be shared.

### Candidate D: UTC timestamp token helpers
- Seen in: `aws_csm_newsletter`, `aws_csm_onboarding` (and conceptually elsewhere).
- Proposed shared path: `MyCiteV2/packages/modules/shared/time_tokens.py`
- Proposed exports:
  - `utc_now_iso(*, seconds_precision: bool = False) -> str`
- Notes: preserve existing precision behavior by adapter function parameters.

### Candidate E: Warning dedupe/aggregation
- Seen in: `fnd_ebi` and `aws_csm_newsletter` (warning list assembly patterns).
- Proposed shared path: `MyCiteV2/packages/modules/shared/warnings.py`
- Proposed exports:
  - `dedupe_warnings(*groups: list[str]) -> list[str]`

## 4) Phased Migration Backlog (Phase 0–5)

Each phase includes rollback and test-gate expectations aligned to `MyCiteV2/tests/contracts/` and `MyCiteV2/tests/adapters/`.

### Phase 0 — Baseline & freeze

Backlog
1. Record baseline on all existing contract and adapter suites.
2. Snapshot representative outputs for: local_audit, aws_narrow_write, aws_read_only_status, fnd_ebi, network_root.
3. Mark currently unused/on-deck modules (`aws_csm_onboarding`, `aws_csm_newsletter`) as “non-runtime critical” but still contract-sensitive.

Rollback note
- No code-path changes; rollback is baseline artifact removal only.

Test gates
- `pytest MyCiteV2/tests/contracts`
- `pytest MyCiteV2/tests/adapters`

### Phase 1 — Shared helper introduction (no call-site switch)

Backlog
1. Add `packages/modules/shared/` helpers for candidates A–E with characterization tests.
2. Keep existing module-local helpers untouched; only import-and-compare tests initially.

Rollback note
- Revert new shared helper package and tests; no runtime behavior change expected.

Test gates
- Full contracts/adapters suites + targeted unit checks for helper parity.

### Phase 2 — Incremental extraction by pattern family

Backlog
1. Switch `local_audit` + `aws_operational_visibility` to shared redaction guard (Candidate C).
2. Switch `aws_csm_onboarding` + `aws_narrow_write` + `local_audit` to shared datum-boundary helper (Candidate B).
3. Switch low-risk modules to shared scalar/warning/time helpers (Candidates A/D/E) one module at a time.

Rollback note
- Preserve old helper names as delegates during each sub-step; rollback by flipping imports back.

Test gates
- After each sub-step: run affected contract tests (`audit_log`, `aws_narrow_write`, `aws_read_only_status`, `fnd_ebi`, `network_root`) and impacted adapter tests.

### Phase 3 — Port tightening and decomposition

Backlog
1. Split `aws_csm_newsletter` into orchestrator + pure payload utilities modules.
2. Remove dead/unused imports (`AwsReadOnlyStatusRequest` in onboarding service).
3. Confirm no cross_domain module imports any adapter implementation directly (enforce architecture test).

Rollback note
- Keep compatibility wrapper in original module path that re-exports moved classes/functions.

Test gates
- Full contracts/adapters suites; focused unit tests for newsletter callbacks/dispatch and onboarding actions.

### Phase 4 — Compatibility pruning (only with green gates)

Backlog
1. Remove module-local duplicate helper implementations replaced by shared utilities.
2. Keep explicit deprecation aliases only when a caller still depends on legacy entrypoint symbols.
3. For `cts_gis`, keep legacy token/document compatibility until explicit contract deprecation is published.

Rollback note
- Restore deprecated aliases and helper delegates if any downstream runtime/test reveals hidden dependency.

Test gates
- Full contracts/adapters suites + architecture boundary tests.

### Phase 5 — Finalization

Backlog
1. Publish final extraction index (what moved where).
2. Document conformance outcomes and unresolved debt list.
3. Re-run full suites and compare against Phase 0 baseline output semantics.

Rollback note
- If final regression appears, revert phase-5 pruning commit while retaining earlier safe extractions.

Test gates
- `pytest MyCiteV2/tests/contracts`
- `pytest MyCiteV2/tests/adapters`
- No newly skipped tests; no undocumented schema/shape drift.

## 5) Exit Criteria Closure Status

| Exit criterion | Status | Notes |
|---|---|---|
| Every audited peripheral module has completed conformance checklist | ✅ complete in this report | Includes inert `external_events` as explicit no-op module.
| Repeated patterns identified and extraction candidates proposed only when repeated in 2+ modules | ✅ complete | Candidates A–E satisfy 2+ rule.
| `tests/contracts` and `tests/adapters` green after final extraction phase | ⏳ pending execution in migration implementation | This report defines required gates and order, not post-refactor run results.
| One-shell behavior unchanged from baseline | ⏳ pending phase execution | Guarded by phased gate + rollback approach above.

## 6) Residual Technical Debt (explicit)

1. **Monolithic newsletter orchestration** (`aws_csm_newsletter`) remains high-complexity and high-side-effect in a single class.
2. **Inconsistent exception taxonomy** across modules (built-in vs domain-specific) without shared error envelope standard.
3. **Inconsistent local `__all__` discipline** (package-level exports are clear, service-module export clarity varies).
4. **Duplicated scalar normalization/time/warning helpers** across many modules.
5. **Potentially stale or unused dependency in onboarding service** (`AwsReadOnlyStatusRequest` import).
6. **Sparse explicit observability contract at module boundary** (telemetry key conventions are implicit and adapter-driven).
7. **No discovered runtime consumers for `aws_csm_onboarding` in scanned runtime modules**, indicating potential dead-path risk unless intentionally staged.

## 7) Recommended Next Action (immediate)

Start Phase 1 with Candidate C (shared forbidden-key walker) because it is:
- low-risk (read/validate-only helper),
- duplicated in at least two modules with near-identical semantics,
- easy to guard using existing contract tests (`audit_log`, `aws_read_only_status`) and adapter tests (`filesystem_audit_log_adapter`, `filesystem_aws_read_only_status_adapter`).
