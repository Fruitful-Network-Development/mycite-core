# MOS SQL Core Master Plan and Cutover Program

Date: 2026-04-21

Doc type: `plan`  
Normativity: `canonical`  
Lifecycle: `completed`  
Last reviewed: `2026-04-21`

## Purpose

Define the single authoritative MOS program for staging, validating, and cutting over to a v1 operational SQL-backed core while keeping unresolved native MOS semantics on explicit adjacent tracks instead of silently treating them as closed canon.

## Scope

In scope:

- one authoritative MOS master program document
- v1 SQL authority staging for approved datum and runtime-adjacent surfaces
- semantic-gap governance for identity, hashing, hyphae, and edit/remap logic
- one lightweight YAML companion index for tasks, gates, dependencies, and evidence
- future-track planning for NIMM/AITAS and directive-context widening

Out of scope for v1 cutover:

- claiming full native MOS standard closure before semantic gates close
- generalized arbitrary datum mutation across the full engine
- migration of non-datum private filesystem assets without stable seams
- promoting tool-local directive-context behavior into shared-engine canon

## Canonical Contract Links

- portal shell contract: `docs/contracts/portal_shell_contract.md`
- route model: `docs/contracts/route_model.md`
- surface catalog: `docs/contracts/surface_catalog.md`
- vocabulary glossary: `docs/contracts/portal_vocabulary_glossary.md`
- CTS-GIS HOPS profile sources: `docs/contracts/cts_gis_hops_profile_sources.md`
- SAMRAS structural model: `docs/contracts/samras_structural_model.md`
- SAMRAS validity and mutation: `docs/contracts/samras_validity_and_mutation.md`

## Current Status Note — 2026-04-21 Final Cut-Over Completion Pass

- **Completed in execution for Track A:** the FND repo copy was inventoried and migrated into `/srv/repo/mycite-core/deployed/fnd/private/mos_authority.sqlite3` through `MyCiteV2/scripts/migrate_fnd_repo_to_mos_sql.py`, with `409` authoritative documents, `3133` authoritative datum rows, `25215` supporting anchor rows, and a passed SQL coverage gate.
- **Completed in execution for Track B:** SQL-backed document version identity, row-level hyphae identity, and deterministic remap semantics remain the canonical semantic layer for the migrated SQL core.
- **Completed in execution for Track C:** additive directive-context snapshots/events remain implemented and non-blocking, and the final migration imported `0` shared directive snapshots and `0` shared directive events because no explicit directive-context manifest was supplied.
- **Completed in runtime cut-over:** migrated `SYSTEM` authority surfaces now fail closed without the authority database instead of silently bootstrapping legacy datum/audit authority, and any retained filesystem helpers are explicitly non-authoritative migration or fixture support only.
- **Completed in UI hardening:** `/portal/system/tools/workbench-ui` now provides a read-only, two-pane SQL-backed spreadsheet with a document table keyed by `version_hash`, a row grid keyed by `hyphae_hash`, additive directive overlay summaries, and no datum-row mutation path.
- **Completed in closure artifacts:** final ingestion, SQL-only activation, directive non-inference, documentation cleanup, the closure checklist, and the overall program-closure audits are published under `docs/audits/reports/`.
- **Retained explicitly as non-blocking exception scope:** `NETWORK` remains a derived-materialization/system-log surface, host-bound private/public assets remain outside SQL datum authority until dedicated ports exist, and future NIMM/AITAS widening requires a separate follow-on plan rather than reopening this master plan.

## Program Authority Rules

1. `docs/plans/master_plan_mos.md` is the single authoritative MOS planning document.
2. `docs/plans/master_plan_mos.index.yaml` is a companion index only. If Markdown and YAML disagree, Markdown wins.
3. Current repo truth governs v1 operational cutover. If personal notes conflict with active contracts, audited behavior, or code seams, the repo wins for v1 and the conflict is logged into the semantic backlog.
4. v1 may be declared an **operational SQL-backed core** before MOS is a fully closed native standard.
5. Native MOS closure cannot be declared until semantic gates `SG-1` through `SG-4` are closed.

## Source Evidence

- `docs/personal_notes/MOS/mos_sql_backed_core_declaration_draft.md`
- `docs/personal_notes/MOS/mycelial_ontological_schema.md`
- `docs/personal_notes/MOS/datum_logic_area_investigation_clarity.md`
- `docs/personal_notes/MOS/mos_novelty_definition.md`
- `docs/audits/cts_gis_datum_handling_alignment_audit_plan_2026-04-20.md`
- `docs/audits/reports/core_portal_datum_mss_protocol_report_2026-04-16.md`
- `docs/audits/reports/peripheral_packages_modularization_report_2026-04-16.md`
- `docs/audits/reports/documentation_ia_audit_report_2026-04-20.md`
- `MyCiteV2/packages/ports/datum_store/contracts.py`
- `MyCiteV2/packages/ports/audit_log/contracts.py`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/instances/_shared/runtime/README.md`

## Logic Authority Matrix

| Rule area | Authority class | Program state | v1 disposition | Notes |
|---|---|---|---|---|
| Portal instance as the authority principal | `canonical` | `stable now` | adopt directly in `Track A` | Supported by current runtime posture and the SQL-core declaration draft. |
| File-owned units remain first-class in the API | `canonical` | `stable now` | preserve file/workbench outward shapes | SQL may replace backing authority without replacing file-oriented contracts. |
| Ordered `layer-value_group-iteration` datum rows | `canonical` | `stable now` | preserve as an operational invariant | Deterministic remap rules are now defined in `SG-3`. |
| Adapter-swap architecture over rewrite | `canonical` | `stable now` | use as the cutover method | Repo audits show port-driven separation is already the right seam. |
| Datum-store reads, audit append/read seams, and tool-exposure/runtime composition as main cutover boundaries | `canonical` | `stable now` | use as initial SQL authority surfaces | No public contract redesign in the first swap. |
| Portal grants and ownership posture boundary | `operational_v1` | `provisional for v1` | add an explicit reusable boundary in `Phase 1` and `Phase 2` | Needed to replace hard-coded capability posture cleanly. |
| `version_hash` and MSS hashing semantics | `canonical` | `stable now` | use `mos.mss_sha256_v1` | Storage-derived document identity is now defined and persisted in SQL. |
| Generalized hyphae-chain derivation and stable semantic identity policy | `canonical` | `stable now` | use `mos.hyphae_chain_v1` | Stable identity is now defined through anchor-context and dependency-closure hashing. |
| Deterministic insert/delete/move remap algorithm | `canonical` | `stable now` | allow bounded authoritative mutation behind SQL datum-store helpers | Canonical write surface is explicit; unsafe deletes are refused instead of guessed. |
| Legacy MSS and historical compatibility paths | `compatibility_only` | `compatibility only` | keep explicit, bounded, and warning-instrumented | Retirement is governed by `SG-4`. |
| Read-only directive-context overlays keyed by semantic identity | `operational_v1` | `stable now` | allow only as additive read models in `Track C` | Overlays may compose shell posture but must never mutate authoritative datum rows. |
| Shared-engine NIMM/AITAS directive semantics | `unresolved` | `unresolved` | keep out of v1 blocker path; route to `Track C` | Remains a design/spec track, not cutover canon. |

## Cutover Scope Table

| Surface or capability area | v1 SQL authority target | Retained outside first cutover | Reason |
|---|---|---|---|
| Authoritative anthology and datum-document reads | `yes` | `no` | Already has stable datum-store seams and file-shaped outward contracts. |
| Contract and reference-resolution metadata | `yes` | `no` | Needed for stable read authority and later semantic closure work. |
| Audit and event append/read store | `yes` | `no` | Already has explicit audit-log seams and bounded responsibilities. |
| Portal grants and ownership posture | `yes` | `no` | Required to replace hard-coded capability defaults with data-backed posture. |
| Tool exposure and configuration metadata | `yes` | `no` | Runtime already composes these as a distinct surface family. |
| Filesystem adapters in shared runtime authority | `no` | `no` | Retired from migrated `SYSTEM` runtime authority in `Phase 7`; retained only as migration/test-only helpers. |
| `NETWORK` system-log workbench and `data/system/system_log.json` derived materialization | `no` | `yes` | The network/system-log surface remains a derived materialization outside SQL datum authority in this program scope. |
| AWS profile stores, hosted manifests, vault/keypass inventory, and other private filesystem assets | `no` | `yes` | They remain host-layout-bound and are not required for the first SQL authority cutover. |
| Generalized arbitrary mutation across datum files | `no` | `yes` | Deferred until deterministic edit/remap semantics close in `SG-3`. |
| `system.tools.workbench_ui` read-only datum grid | `yes` | `no` | It materializes SQL-backed datum semantics and additive directive overlays without mutating authoritative rows. |
| Shared-engine NIMM/AITAS widening | `no` | `yes` | Deferred to `Track C` and explicitly not a v1 blocker. |

## Interface and Boundary Rules

- Preserve existing public datum-store and audit-log contracts during the initial SQL swap.
- Treat adapter replacement as the first implementation target, not contract redesign.
- Add one explicit portal-authority boundary for grants, ownership posture, and tool-exposure metadata if the current runtime composition does not already expose one cleanly enough.
- Keep shell and runtime public behavior unchanged in v1. File and workbench-oriented surfaces remain first-class, and SQL must project back into the same outward shapes.
- For migrated `SYSTEM` authority surfaces, shared runtime must require an initialized authority database and fail closed rather than silently falling back to filesystem datum/audit authority.
- Shared directive snapshots/events may be imported only from an explicit migration manifest; absent that manifest, directive-context counts must remain zero and the reports must say so.
- Use `docs/audits/cts_gis_datum_handling_alignment_audit_plan_2026-04-20.md` as the main operational dependency for ordering, MSS-compatibility, hyphae/address semantics, and projection parity evidence.

## Track A — V1 Operational SQL-Backed Core Cutover

### Phase 0 — Evidence Consolidation and Program Baseline

Required outputs:

- this master plan as the authoritative program document
- a logic authority matrix mapping every major MOS claim to `canonical`, `operational_v1`, `compatibility_only`, or `unresolved`
- a semantic gap register covering hashing, hyphae, edit/remap, and closure criteria
- a cutover scope table listing every v1 SQL-owned surface and every filesystem-retained surface with reasons
- `docs/plans/master_plan_mos.index.yaml` as the companion index

Phase exit:

- every major MOS claim is classified and no cutover milestone relies on an unclassified rule

### Phase 1 — Define the V1 SQL Authority Surface

Approved v1 SQL authority surfaces:

- authoritative anthology and datum-document reads
- contract and reference-resolution metadata
- audit and event append/read store
- portal grants and ownership posture
- tool exposure and configuration metadata

Required restrictions:

- keep non-datum private filesystem assets out of the first cutover unless they already have stable seams
- keep generalized write authority out of v1 until `SG-3` is closed
- preserve file-shaped outward contracts and shell behavior

Phase exit:

- every approved v1 SQL surface has a named owner, a backing seam, and an explicit exclusion list

### Phase 2 — Shadow-Mode SQL Adapter Design

Required work:

- design SQL-backed adapters behind the existing datum-store and audit/event seams
- design the portal-authority boundary for grants, ownership posture, and tool-exposure metadata
- confine legacy filesystem projections to bootstrap, parity evidence, or fixture support outside active runtime authority
- define rollback posture before any authority promotion

Phase exit:

- shadow-mode topology is documented and no public contract redesign is required to compare SQL behavior against non-authoritative legacy evidence

### Phase 3 — Parity and Rollback Readiness

Required comparisons:

- anthology and document reads
- audit append and read flows
- tool exposure posture
- grant and ownership posture

Required posture:

- legacy filesystem comparisons remain available only as non-authoritative parity evidence
- parity drift is tracked explicitly with owner and remediation path
- rollback path is documented before SQL becomes primary

Phase exit:

- representative SQL-versus-legacy paths compare cleanly enough to promote approved surfaces without losing rollback safety

### Phase 4 — Promote SQL to Primary Authority

Required work:

- promote SQL to primary authority only for approved v1 surfaces
- keep outward shell and runtime behavior unchanged
- keep retained filesystem surfaces explicitly outside the SQL authority claim
- keep compatibility paths bounded and warning-instrumented where they remain

Phase exit:

- approved surfaces are SQL-primary and retained filesystem surfaces are still documented as retained, not forgotten

### Phase 5 — Remove Hard-Coded FND Capability Defaults

Required work:

- replace hard-coded FND capability defaults only after DB-backed grants reproduce the same effective operational posture
- verify tool exposure and capability gating still match expected runtime behavior

Phase exit:

- runtime posture is grant-derived rather than default-derived for the approved surfaces, with no behavior regression in effective access posture

### Phase 6 — FND Repo Ingestion and SQL Authority Coverage

Required work:

- add one official migration CLI at `MyCiteV2/scripts/migrate_fnd_repo_to_mos_sql.py`
- inventory every file under `deployed/fnd/data/**` into `authoritative_import`, `supporting_anchor_context`, `derived_materialization`, or `explicit_exception`
- write through existing SQL ports/adapters rather than duplicating persistence logic
- compute `version_hash` and `hyphae_hash` only through the Track B semantics path
- emit JSON and Markdown ingestion reports with counts, coverage status, retained exception scope, and failures
- enforce the coverage rule that no authoritative FND datum row is considered migrated unless it is present in SQL semantics or explicitly exception-listed with rationale

Phase exit:

- the FND repo copy is ingested into the SQL-backed core and every authoritative datum row is accounted for by SQL semantics or an explicit retained-scope declaration

### Phase 7 — SQL-Only Runtime Activation and Legacy Retirement

Required work:

- switch migrated `SYSTEM` shared-runtime composition to SQL-only authority
- remove public shared-runtime support for `filesystem` and `shadow` authority modes on migrated surfaces
- fail closed when the authority database or required snapshots are missing
- remove shared-runtime dependence on filesystem datum/audit authority adapters
- retain filesystem parsing logic only where migration or fixture tests still need it, and keep that code explicitly non-authoritative

Phase exit:

- migrated `SYSTEM` surfaces no longer consume filesystem datum/audit authority in shared runtime, and remaining filesystem code is explicitly non-authoritative migration/test-only support rather than active authority

### Phase 8 — Minimal SQL-Backed Workbench UI Hardening

Required work:

- add `MyCiteV2/packages/tools/workbench_ui/` as a shell-attached, script-backed tool package
- expose `/portal/system/tools/workbench-ui` as the utilitarian SQL-backed two-pane spreadsheet surface
- keep the first pass read-only, spreadsheet-like, and additive-only with respect to directive overlays
- provide a document table keyed by `version_hash` plus a selected-document row grid keyed by `hyphae_hash`
- keep backward-compatible row-grid query keys (`filter`, `sort`, `dir`) while adding document-pane query keys (`document_filter`, `document_sort`, `document_dir`)
- keep file/workbench behavior intact while reusing the existing shell region model

Phase exit:

- the repo has a stable, read-only SQL-backed workbench UI that surfaces document/version selection, row semantics, and additive directive overlays without introducing datum mutation authority

## Track B — Semantic Closure Gates

| Gate | Required closure | What it blocks | Minimum evidence |
|---|---|---|---|
| `SG-1` | version identity and MSS hashing policy | full native MOS closure and durable SQL-side version identity claims | hash input definition, canonicalization policy, compatibility policy for historical forms |
| `SG-2` | hyphae derivation and stable semantic identity policy | full native MOS closure and stable semantic identity claims | derivation algorithm, identity/storage distinction rules, edge-case matrix |
| `SG-3` | deterministic edit/remap algorithm for insert, delete, and move | generalized mutation authority in SQL-backed core | transactional remap rules, preview/apply policy, reference-shift invariants |
| `SG-4` | standard-closure declaration criteria and compatibility retirement rules | declaration of closed native MOS standard | closure checklist, retirement thresholds, compatibility shutdown policy |

Semantic gap register:

- `SG-1`: closed by `docs/plans/mos_sg1_version_identity_policy_2026-04-21.md`
- `SG-2`: closed by `docs/plans/mos_sg2_hyphae_derivation_policy_2026-04-21.md`
- `SG-3`: closed by `docs/plans/mos_sg3_edit_remap_policy_2026-04-21.md`
- `SG-4`: closed by `docs/plans/mos_sg4_standard_closure_policy_2026-04-21.md`

## Track C — Directive-Context Design and Spec Track

Purpose:

- define how NIMM/AITAS and broader directive-context ideas could later widen the engine without blocking the v1 SQL cutover

Required outputs:

- future insertion-point map for shared shell, domain, and tool-local boundaries
- schema candidates keyed to `hyphae_hash` and `version_hash`
- update and conflict-policy posture for directive snapshots
- approved additive runtime seams for reading normalized directive overlays
- explicit non-goals for v1
- list of behaviors that remain tool-local until a later design approval
- dependency notes showing where directive-context work depends on `SG-2` and `SG-3`

Current defaults:

- do not treat current CTS-GIS tool-local mediation behavior as shared-engine canon
- do not redesign the shared shell around directive-context semantics in v1
- do not block SQL cutover on directive-context closure
- do allow approved read-only overlay seams that depend on Track B semantic identities and preserve file/workbench behavior
- do require an explicit migration manifest before any shared directive snapshots/events may be imported into SQL authority

## YAML Companion Workflow

`docs/plans/master_plan_mos.index.yaml` exists to improve execution and evidence tracking without becoming a second plan document.

Required fields for each entry:

- `track`
- `phase`
- `status`
- `dependencies`
- `gates`
- `evidence_refs`

Optional freeform fields:

- `notes`
- `open_questions`
- `rationale`

Companion rules:

- Markdown is authoritative.
- YAML should stay lightweight and index-like.
- YAML may add exploratory notes without forcing schema churn for every new question.
- YAML must keep dependency and evidence links explicit enough for agent and audit workflows.

## Validation Gates

1. **Authority mapping completeness gate**
   - Every major MOS claim is mapped to `canonical`, `operational_v1`, `compatibility_only`, or `unresolved`.
2. **Cutover scope completeness gate**
   - Every v1 SQL-owned surface and every retained filesystem surface is listed with a reason.
3. **Shadow parity gate**
   - SQL and filesystem behavior are compared on representative anthology/document reads, audit flows, tool exposure posture, and grant posture.
4. **Semantic discipline gate**
   - No phase assumes hashing, hyphae derivation, or generalized edit/remap semantics are solved without closing the matching semantic gate.
5. **YAML integrity gate**
   - The companion YAML keeps dependency and evidence links intact while remaining lightweight enough for exploratory work.
6. **Native closure gate**
   - MOS cannot be declared a closed native standard until `SG-1` through `SG-4` are closed.
7. **Directive overlay non-mutation gate**
   - Directive context remains additive, keyed to `version_hash`/`hyphae_hash`, and must not rewrite authoritative datum rows or block file/workbench fallbacks.
8. **SQL authority ingestion coverage gate**
   - Every authoritative FND datum row is present in SQL document/row semantics or is explicitly exception-listed with a reason.
9. **SQL-only authority activation gate**
   - Migrated `SYSTEM` surfaces fail closed without an initialized authority database and do not advertise filesystem/shadow runtime authority modes.
10. **Directive overlay non-inference gate**
   - Shared directive snapshots/events are imported only from an explicit manifest and remain zero when no manifest is supplied.
11. **Documentation alignment gate**
   - Active docs describe SQL-backed authority for migrated surfaces, preserve historical evidence as superseded artifacts, and avoid creating competing master plans.

## Risks

1. **Semantic leakage risk**
   - Mitigation: unresolved identity and mutation rules stay on explicit gates instead of being implied into v1.
2. **Contract drift risk**
   - Mitigation: preserve public datum-store and audit-log contracts during the initial SQL swap.
3. **Runtime posture regression risk**
   - Mitigation: keep FND capability default removal until DB-backed grants reproduce the same effective posture.
4. **YAML over-formalization risk**
   - Mitigation: keep Markdown authoritative and limit YAML to indexing, dependency, and evidence support.
5. **Migration coverage risk**
   - Mitigation: the FND cut-over cannot close until ingestion reports prove document/row semantic coverage or explicit retained-scope classification.
6. **Historical-document confusion risk**
   - Mitigation: retain intermediate reports only as superseded evidence and publish one final closure report that names the current authoritative posture.

## Exit Criteria

V1 operational SQL-backed core exit:

- approved v1 SQL surfaces are explicitly defined, shadowed, and promoted with rollback posture
- retained exception surfaces are explicitly documented rather than implicitly deferred
- outward shell and runtime behavior remains file and workbench-oriented
- hard-coded FND capability defaults are removed only after grant-derived parity is proven, or are explicitly deferred with rationale

Native MOS closure exit:

- `SG-1` through `SG-4` are closed
- compatibility retirement policy is published
- unresolved semantic claims no longer remain in the semantic gap register

## Closure Status — 2026-04-21

- Track A completion (`Phase 0` through `Phase 8`): **Met**
- FND ingestion coverage gate: **Met**
- SQL-only activation gate for migrated `SYSTEM` surfaces: **Met**
- Workbench UI read-only SQL surface: **Met**
- Track B semantic closure (`SG-1` through `SG-4`): **Met**
- Track C additive-only directive overlay implementation (`MOS-C2`): **Met and intentionally non-blocking**
- Documentation alignment, closure-corpus review, and historical cleanup: **Met**

Program close-out posture:

- SQL-authoritative now:
  - authoritative anthology and sandbox source documents
  - SQL document and row semantic identity
  - system workbench and publication summary snapshots
  - portal grants, ownership posture, and tool-exposure metadata
  - audit-log append/read storage
  - additive directive-context snapshots/events
  - the read-only `workbench_ui` SQL datum grid
- Explicit retained exception scope:
  - `NETWORK` / `system_log.json` as a derived-materialization surface
  - host-bound private/public assets without dedicated ports
  - future shared-engine NIMM/AITAS widening beyond the additive Track C seam
- Final authoritative closure evidence:
  - `docs/audits/reports/mos_fnd_sql_ingestion_coverage_report_2026-04-21.md`
  - `docs/audits/reports/mos_sql_only_authority_activation_and_legacy_retirement_2026-04-21.md`
  - `docs/audits/reports/mos_directive_context_non_inference_validation_2026-04-21.md`
  - `docs/audits/reports/mos_documentation_alignment_and_cleanup_2026-04-21.md`
  - `docs/audits/reports/mos_program_closure_report_2026-04-21.md`
