# Core Portal Datum/MSS Protocol Audit Report

Date: 2026-04-16  
Source checklist: `docs/audits/core_portal_datum_mss_protocol_audit_plan_2026-04-16.md`

## Current status note — 2026-04-20 foundation-first pass

- **Closed in code:** publication-domain strictness, `PublicationProfileBasicsWriteResult.schema`, malformed `NetworkRootReadModelRequest.surface_query` rejection, and NETWORK unknown-key warnings.
- **Still active and worth doing now:** no protocol blocker from the original F1-F4 set remains after the foundation-first pass.
- **Deferred:** broader producer/consumer compatibility-matrix work remains backlog and is not part of this pass.

## Audit method

- Contract-first sweep executed in plan order: **Create → Read → Project → Render**.
- Evidence sources:
  - Static inspection of contracts/adapters/runtime/host+client files.
  - Targeted contract probes via Python for request/result boundary behavior.

---

## 1) Datum Lifecycle Checkpoints

## 1A. Create checkpoint

### Verification target: `PublicationProfileBasicsWriteRequest` and `PublicationProfileBasicsWriteResult`

- **FAIL** — Request enforces required fields (`tenant_id`, `tenant_domain`, `profile_title`) but domain validation is too permissive (`"." in tenant_domain` only). Inputs like `bad/domain.com` and `bad..domain.com` are currently accepted.
  - Evidence (code): `PublicationProfileBasicsWriteRequest.__post_init__` validates only presence + dot semantics.
  - Evidence (probe):
    - `bad/domain.com => OK bad/domain.com`
    - `bad..domain.com => OK bad..domain.com`
- **FAIL** — Write result does not expose a schema/version constant, contrary to strict schema tagging expectations for write confirmations.
  - Evidence: `PublicationProfileBasicsWriteResult.to_dict()` returns `{source, resolution_status, warnings}` without `schema`.

### Verification target: `PublicationTenantSummarySource` construction and normalization paths

- **FAIL** — Similar domain permissiveness (`"."`-only check) allows non-plain domains; this weakens canonical identity normalization at source boundary.
- **PASS** — Required fields (`tenant_id`, `tenant_domain`, `profile_id`) are enforced; optional profiles are normalized to JSON object-or-null.

### Verification target: adapter/service glue mapping portal payloads into write requests

- **PASS (with caveat)** — `run_system_profile_basics_action()` routes portal payload into `PublicationProfileBasicsService.write_profile_basics(...)` and ultimately `PublicationProfileBasicsWriteRequest`, preserving required field enforcement.
- **FAIL (carry-through from contract weakness)** — Because domain checks are weak in port contracts, glue path still permits malformed domain-like values.

---

## 1B. Read checkpoint

### Verification target: `SystemDatumStoreRequest`, `SystemDatumWorkbenchResult`

- **PASS** — Request boundary rejects non-dict payloads and missing tenant id.
- **PASS** — Workbench `raw`/metadata payloads are JSON-serializable, and `ok` semantics are explicit (`row_count > 0` and `materialization_status["canonical_source"] == "loaded"`).

### Verification target: `AuthoritativeDatumDocumentRequest`, `AuthoritativeDatumDocumentCatalogResult`

- **PASS** — Non-dict payloads rejected; required fields validated; metadata/rows normalized with deterministic field-specific errors.
- **PASS** — Catalog `ok` semantics are explicit (`document_count > 0` and readiness marker).

### Verification target: `NetworkRootReadModelRequest` / `Result`

- **FAIL** — `from_dict()` does **not** reject malformed `surface_query` types; non-dict values are silently coerced to `None`, then normalized to `{}`.
  - Probe evidence: `malformed_surface_query_type => NO_ERROR`.
- **PASS** — `portal_tenant_id` required/lowercased; `portal_domain` validated as plain domain-like (rejects slash, backslash, `..`).
- **PASS** — `found` is derived from `source` presence; not independently authored.

### Verification target: `FndEbiReadOnlyRequest` / `Result`

- **PASS** — Request boundary validates tenant id, optional domain form, and `YYYY-MM` when provided.
- **PASS** — `found` derived from source presence; source payload enforces non-empty dict semantics.

---

## 1C. Project checkpoint

### Verification target: `packages/modules/cross_domain/network_root/service.py`

- **PASS** — Service reads from source payload and projects to UI model; query-driven fields map to `active_filters` and selection state.
- **PASS (with caution)** — Projection mostly builds derived view-only structure and preserves canonical-ish record payload under `raw`.

### Verification target: `packages/adapters/filesystem/network_root_read_model.py`

- **PASS** — Query-level filtering is constrained to `contract`, `type`, `record` and fixed `view=system_logs`.
- **FAIL** — Unknown query-key policy is currently implicit silent drop in `_normalize_surface_query()`; no warnings or codified behavior is emitted.
- **PASS** — Output payload remains envelope-compatible with `NetworkRootReadModelSource.payload` non-empty dict contract.

### Verification target: portal runtime orchestration `instances/_shared/runtime/portal_shell_runtime.py`

- **PASS** — Network surface request path transmits `portal_instance_id`, `portal_domain`, and `surface_query` to runtime service in canonical flow.
- **PASS** — No evidence of canonical store mutation in projection path.

### Legacy alias compatibility check (CTS-GIS phase-A)

- **PASS** — Alias helpers and warning code are isolated in `ports/datum_store/cts_gis_legacy_compat.py`; filesystem datum adapter emits legacy warning code when consumed.

---

## 1D. Render checkpoint

### Verification target: `instances/_shared/portal_host/app.py`

- **PASS** — Host shell endpoint delegates to runtime envelope; network route bootstraps shell with query forwarding.

### Verification target: `instances/_shared/portal_host/static/v2_portal_network_workspace.js`

- **PASS** — Renderer consumes payload by named fields with safe fallback values (`|| "—"`, empty states, null guards).
- **PASS** — Missing optional fields degrade safely (inspector renders guidance when `selected_record` absent).

### Verification target: `instances/_shared/portal_host/static/v2_portal_aws_workspace.js`

- **PASS** — Field access uses guarded defaults throughout; optional omissions do not crash renderer path.

---

## 2) Contract/Payload Compatibility Test Matrix

| Matrix item | Evidence | Outcome |
|---|---|---|
| Contract round-trip: minimal request | `NetworkRootReadModelRequest.from_dict({'portal_tenant_id':'FND'}).to_dict()` -> `{'portal_tenant_id':'fnd','portal_domain':''}` | **PASS** |
| Contract round-trip: full request | Full payload retains normalized domain + query keys (`view/contract/type/record`) | **PASS** |
| Contract round-trip: malformed types | `surface_query='bad'` returns **NO_ERROR** (silently dropped) | **FAIL** |
| Envelope parity | `NetworkRootReadModelSource.from_dict({'payload':{}})` and `FndEbiReadOnlySource.from_dict({'payload':{}})` both reject empty dict | **PASS** |
| Payload evolution: additive fields | `NetworkRootReadModelSource`/`FndEbiReadOnlySource` accept arbitrary JSON-serializable payload members | **PASS** |
| Payload evolution: nullable→required gate | Source payload already enforces non-empty dict; transition to required at source is already strict | **PASS** |

---

## 3) Failure-mode Checklist (explicit outcomes)

## Malformed payload

- [x] Reject non-dict request payloads at `from_dict` boundaries.  
  **Outcome:** pass across audited request contracts.
- [x] Reject payload objects with empty-string keys after trimming.  
  **Outcome:** pass in JSON normalization helpers (`_normalize_json_value`).
- [x] Reject source payloads that are empty dicts where non-empty is required.  
  **Outcome:** pass for `NetworkRootReadModelSource.payload` and `FndEbiReadOnlySource.payload`.
- [~] Confirm malformed nested JSON values fail with deterministic error messages.  
  **Outcome:** pass for normalized JSON paths; not fully exhaustively tested for every nested structure variant.

## Version mismatch

- [~] Assert schema/version constants emitted on datum documents/workbench payloads where defined.  
  **Outcome:** mixed — pass for workbench/document contracts; gap for `PublicationProfileBasicsWriteResult` (no schema field).
- [ ] Introduce compatibility matrix for producer vs consumer version.  
  **Outcome:** **not implemented** in audited code surfaces.
- [x] Warning-path behavior for known legacy aliases while preserving canonical outward schemas.  
  **Outcome:** pass (CTS-GIS legacy warning code path present).
- [x] Ensure no silent downgrade when unknown schema/version is received.  
  **Outcome:** partial pass at envelope level; schema mismatch handling exists in host runtime response path.

## Missing contract fields

- [x] Required identity fields fail fast.  
  **Outcome:** pass broadly; exception: domain strictness is weak in publication write/summary contracts.
- [~] Required routing/query fields validated before projection.  
  **Outcome:** mixed — accepted query keys normalized, but malformed `surface_query` type is not rejected at `NetworkRootReadModelRequest.from_dict`.
- [x] Missing optional fields produce explicit defaults (`""`, `{}`, `None`) per contract.  
  **Outcome:** pass across audited request/result contracts.
- [ ] Renderer behavior for absent optional fields covered by regression tests.  
  **Outcome:** no explicit regression test evidence gathered in this audit run.

### Impacted symbols/files (from failures)

- `PublicationProfileBasicsWriteRequest.__post_init__` (`tenant_domain` validation).  
  File: `MyCiteV2/packages/ports/datum_store/contracts.py`
- `PublicationTenantSummarySource.__post_init__` (`tenant_domain` validation).  
  File: `MyCiteV2/packages/ports/datum_store/contracts.py`
- `PublicationProfileBasicsWriteResult.to_dict` / class schema omission.  
  File: `MyCiteV2/packages/ports/datum_store/contracts.py`
- `NetworkRootReadModelRequest.from_dict` (`surface_query` malformed type accepted).  
  File: `MyCiteV2/packages/ports/network_root_read_model/contracts.py`
- `_normalize_surface_query` unknown key policy not surfaced/warned.  
  File: `MyCiteV2/packages/adapters/filesystem/network_root_read_model.py`

---

## 4) Mismatch Classification and Ownership

| ID | Mismatch | Classification | Owner | Severity | Recommended fix boundary |
|---|---|---|---|---|---|
| F1 | `NetworkRootReadModelRequest.from_dict` silently accepts non-dict `surface_query` | implementation bug | Ports (read-model contracts) | High | `ports/network_root_read_model/contracts.py` (+ contract tests) |
| F2 | Domain validation in publication contracts accepts slash/double-dot forms | contract bug | Ports (datum_store contracts) | High | `ports/datum_store/contracts.py` (+ shared domain validator helper) |
| F3 | `PublicationProfileBasicsWriteResult` missing schema/version tagging | contract bug | Ports (datum_store contracts) | Medium | `ports/datum_store/contracts.py` + downstream fixture updates |
| F4 | Unknown network query keys silently dropped; policy not codified/observable | migration gap | Adapters + Runtime | Medium | `adapters/filesystem/network_root_read_model.py` + runtime warning plumbing |

---

## 5) Compatibility Migration Strategy (Phase A / Phase B)

## Phase A (additive compatibility + warning instrumentation)

1. **Harden request parsing without immediate breakage**
   - Keep accepting existing valid payloads.
   - Add warning emission when unknown query keys are present.
   - Add warning emission when legacy alias/value forms are consumed.
2. **Introduce strict domain helper (shared)**
   - Implement one canonical plain-domain validator for publication + network contracts.
   - Gate only clearly invalid forms first; emit warnings where tolerated temporarily.
3. **Schema tagging rollout for write confirmations**
   - Add `schema` to `PublicationProfileBasicsWriteResult`.
   - Update adapter/runtime fixtures and snapshot tests.
4. **Deprecation window (Phase A)**
   - Minimum **2 releases or 60 days** (whichever is longer) with warnings enabled.

## Phase B (deprecation enforcement)

1. Enforce strict rejection for malformed `surface_query` types at `from_dict` boundary.
2. Enforce strict plain-domain validation on publication contracts.
3. Remove temporary alias/warning-only pathways once warning volume reaches agreed threshold.
4. **Deprecation window (Phase B cutoff)**
   - Announce cutoff at least **1 release / 30 days** in advance.
   - Require green contract matrix + updated fixtures before enforcement merge.

---

## Executive Summary

- **Historical audit findings:** 4
  - High: 2
  - Medium: 2
- **Current repo status after the 2026-04-20 foundation-first pass:** the original F1-F4 blockers are closed in code.
- **Go/No-Go recommendation:** the original audit-time **NO-GO** recommendation is historical and no longer reflects the current repository state.
