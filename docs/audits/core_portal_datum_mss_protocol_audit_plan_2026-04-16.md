# Core Portal Datum/MSS Protocol Audit Plan

Date: 2026-04-16

## Objective

Define and execute a protocol audit for datum lifecycle handling and MSS/portal-network payload compatibility across V2 ports, runtime projection paths, and read-model surfaces.

## In-Scope Interfaces

- Datum/store contracts under `MyCiteV2/packages/ports/datum_store/`
- Network-root read-model contracts under `MyCiteV2/packages/ports/network_root_read_model/`
- Related read-model payload contracts used by portal views (notably `fnd_ebi_read_only`)
- Runtime projection paths that convert store rows/documents into portal-facing payloads

## 1) Datum Lifecycle Checkpoints (Create / Read / Project / Render)

### A. Create checkpoint (authoritative datum ingress)

Audit focus:
- Validate all create/write entry points normalize required identity fields (`tenant_id`, `tenant_domain`, profile identifiers).
- Verify strict schema tagging for authored document/result payloads and write confirmation payloads.
- Ensure write-side requests reject non-domain-like tenant domains and missing required profile title / ids.

Verification targets:
- `PublicationProfileBasicsWriteRequest` and `PublicationProfileBasicsWriteResult`
- `PublicationTenantSummarySource` construction and normalization paths
- Any adapter/service glue that maps portal payloads into write requests

Pass criteria:
- Every write request fails fast on missing required fields.
- Every write result emits normalized source + resolution status and optional warnings.

### B. Read checkpoint (store contract boundary)

Audit focus:
- Confirm read request contract parsing uses canonicalized tenant/domain normalization and type checks.
- Confirm row/document models enforce JSON-serializable `raw`/metadata payload boundaries.
- Confirm catalog/workbench `ok` semantics are stable and contractually explicit.

Verification targets:
- `SystemDatumStoreRequest`, `SystemDatumWorkbenchResult`
- `AuthoritativeDatumDocumentRequest`, `AuthoritativeDatumDocumentCatalogResult`
- `NetworkRootReadModelRequest` / `Result`
- `FndEbiReadOnlyRequest` / `Result`

Pass criteria:
- Non-dict payloads, malformed keys, and invalid domain-like fields are rejected.
- `found`/`ok` flags match documented readiness/materialization semantics.

### C. Project checkpoint (runtime projection)

Audit focus:
- Trace projection from store rows/documents into runtime model payloads used by NETWORK and portal workspaces.
- Confirm projection owns query-level filtering only (`view`, `contract`, `type`, `record`) and does not mutate canonical source records.
- Verify legacy alias handling (e.g., CTS-GIS phase-A aliases) remains compatibility-only and warning-emitting.

Verification targets:
- `packages/modules/cross_domain/network_root/service.py`
- `packages/adapters/filesystem/network_root_read_model.py`
- portal runtime orchestration in `instances/_shared/runtime/portal_shell_runtime.py`

Pass criteria:
- Projection output remains schema-compatible with read-model source payload contracts.
- Compatibility aliases are isolated and observable through warning codes.

### D. Render checkpoint (portal-network client payload consumption)

Audit focus:
- Verify host/client exchange sends canonical `surface_query` and tenant scope values.
- Verify client renderers assume payload-by-contract rather than positional fields.
- Confirm missing optional fields degrade safely without runtime crashes.

Verification targets:
- `instances/_shared/portal_host/app.py`
- `instances/_shared/portal_host/static/v2_portal_network_workspace.js`
- `instances/_shared/portal_host/static/v2_portal_aws_workspace.js`

Pass criteria:
- Render layers only consume fields guaranteed by contract.
- Contract mismatch results in explicit fallback states, not silent partial rendering.

## 2) Network Payload Contract Checks (Portal-Network Communication)

### Contract checklist

- Request envelope checks:
  - `portal_tenant_id` required, normalized lowercase.
  - `portal_domain` optional but validated as plain domain-like when present.
  - `surface_query` must be object/dict with non-empty keys.
- Response envelope checks:
  - `source` nullable; when present must include non-empty payload object.
  - `found` must be derivable from source presence, not independently authored.
- Compatibility checks:
  - Query tokens used by portal clients (`view`, `contract`, `type`, `record`) are accepted and projected consistently.
  - Unrecognized query keys are either ignored by policy or surfaced via warnings (decide and codify).

### Contract/payload compatibility test matrix

- Contract-to-adapter round-trip (`from_dict` -> adapter read -> `to_dict`) for:
  - minimal request
  - full request with `surface_query`
  - malformed request types
- Payload evolution checks:
  - additive field introduction remains backward compatible
  - nullable-to-required transitions are blocked without migration gates
- Cross-port envelope parity:
  - `NetworkRootReadModelSource.payload` and `FndEbiReadOnlySource.payload` both enforce non-empty dict semantics

## 3) Correlation Table: Datum/Store Ports and Related Read-Model Ports

| Port package | Primary request contract | Primary result/source contract | Lifecycle stage | Notes for audit |
|---|---|---|---|---|
| `ports/datum_store` (`SystemDatumStorePort`) | `SystemDatumStoreRequest` | `SystemDatumWorkbenchResult` + `SystemDatumResourceRow` | Read -> Project | Validate workbench materialization status + `ok` semantics before projection. |
| `ports/datum_store` (`AuthoritativeDatumDocumentPort`) | `AuthoritativeDatumDocumentRequest` | `AuthoritativeDatumDocumentCatalogResult` + document/row models | Create/Read -> Project | Validate strict document metadata/row JSON serializability and source-kind constraints. |
| `ports/datum_store` (`PublicationTenantSummaryPort`) | `PublicationTenantSummaryRequest` | `PublicationTenantSummaryResult` + `PublicationTenantSummarySource` | Read -> Render | Validate tenant/domain normalization and nullable source behavior. |
| `ports/datum_store` (`PublicationProfileBasicsWritePort`) | `PublicationProfileBasicsWriteRequest` | `PublicationProfileBasicsWriteResult` | Create -> Read-after-write | Confirm bounded write semantics and post-write source projection consistency. |
| `ports/network_root_read_model` (`NetworkRootReadModelPort`) | `NetworkRootReadModelRequest` | `NetworkRootReadModelResult` + `NetworkRootReadModelSource` | Read -> Project -> Render | Core portal-network payload gate; verify query normalization and non-empty payload requirement. |
| `ports/fnd_ebi_read_only` (`FndEbiReadOnlyPort`) | `FndEbiReadOnlyRequest` | `FndEbiReadOnlyResult` + `FndEbiReadOnlySource` | Read -> Render | Secondary read-model parity check for envelope compatibility and domain/year-month validation. |

## 4) Failure-Mode Checklist

### Malformed payload

- [ ] Reject non-dict request payloads at `from_dict` boundaries.
- [ ] Reject payload objects with empty-string keys after trimming.
- [ ] Reject source payloads that are empty dicts where non-empty is required.
- [ ] Confirm malformed nested JSON values fail with deterministic error messages.

### Version mismatch

- [ ] Assert schema/version constants are emitted on datum documents/workbench payloads where defined.
- [ ] Introduce compatibility matrix for producer version vs consumer expectation.
- [ ] Add warning-path behavior for known legacy aliases while preserving canonical outward schemas.
- [ ] Ensure no silent downgrade when unknown schema/version is received.

### Missing contract fields

- [ ] Required identity fields (`tenant_id`, `portal_tenant_id`, `profile_id`, etc.) fail fast.
- [ ] Required routing/query fields for specific views are validated before projection.
- [ ] Missing optional fields produce explicit defaults (`""`, `{}`, or `None`) per contract.
- [ ] Renderer behavior for absent optional fields is covered by regression tests.

## 5) Deliverable

## Protocol hardening recommendations

Planned output:
1. Consolidated contract invariants list (per port) with shared normalization helpers where duplication exists.
2. Explicit payload envelope policy for portal-network communication (required/optional fields, unknown-key policy, warning policy).
3. Regression test expansion across contract tests, adapter unit tests, and end-to-end portal host interaction tests.
4. Observability recommendations: warning code inventory + structured audit logs for contract failures.

## Compatibility migration strategy

Planned output:
1. Versioned compatibility matrix for each read-model payload contract.
2. Two-phase migration template:
   - Phase A: additive compatibility + warning instrumentation.
   - Phase B: removal of deprecated aliases/fields after bounded release window.
3. Backfill and replay strategy for persisted payload artifacts (if historical data requires normalization).
4. Release checklist requiring contract test green status and payload fixture updates before deprecation enforcement.

## Execution Notes

- Run this audit as a contract-first sweep: ports -> adapters -> runtime -> host/client render.
- Treat all payload shape assumptions as explicit contract requirements (or remove them).
- Capture every discovered mismatch as either:
  - contract bug (fix contract/tests), or
  - implementation bug (fix adapter/runtime/renderer), or
  - migration gap (add phased compatibility plan).
