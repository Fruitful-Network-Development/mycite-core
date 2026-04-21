# MOS SQL Core Master Plan and Cutover Program

Date: 2026-04-21

Doc type: `plan`  
Normativity: `canonical`  
Lifecycle: `active`  
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

## Current Status Note — 2026-04-21 Closure Pass

- **Completed in code for Track A:** a bounded portal-authority read seam, SQLite-backed SQL adapters for datum-store/audit/portal-authority surfaces, and runtime authority modes `filesystem`, `shadow`, and `sql_primary`.
- **Completed in code for Track B:** SQL-backed document version identity storage, row-level hyphae/semantic identity storage, and deterministic insert/delete/move remap helpers behind the datum-store adapter.
- **Completed in validation for Track A and Track B:** SQL-versus-filesystem parity coverage for the approved cutover surfaces plus dedicated regression coverage for version hashing, hyphae derivation, and edit/remap behavior.
- **Completed in program artifacts:** dedicated closure artifacts for `SG-1` through `SG-4`, an updated semantic gate register, and a widened Track C directive-context design track.
- **Still non-blocking by design:** NIMM/AITAS widening remains a parallel design/spec track rather than a prerequisite for the SQL-backed core or Track B closure.

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
| Shared-engine NIMM/AITAS directive semantics | `unresolved` | `unresolved` | keep out of v1 blocker path; route to `Track C` | Remains a design/spec track, not cutover canon. |

## Cutover Scope Table

| Surface or capability area | v1 SQL authority target | Retained outside first cutover | Reason |
|---|---|---|---|
| Authoritative anthology and datum-document reads | `yes` | `no` | Already has stable datum-store seams and file-shaped outward contracts. |
| Contract and reference-resolution metadata | `yes` | `no` | Needed for stable read authority and later semantic closure work. |
| Audit and event append/read store | `yes` | `no` | Already has explicit audit-log seams and bounded responsibilities. |
| Portal grants and ownership posture | `yes` | `no` | Required to replace hard-coded capability defaults with data-backed posture. |
| Tool exposure and configuration metadata | `yes` | `no` | Runtime already composes these as a distinct surface family. |
| Filesystem adapters as compatibility projections | `no` | `yes` | Needed for shadow-mode parity, rollback posture, and compatibility containment. |
| AWS profile stores, hosted manifests, vault/keypass inventory, and other private filesystem assets | `no` | `yes` | They remain host-layout-bound and are not required for the first SQL authority cutover. |
| Generalized arbitrary mutation across datum files | `no` | `yes` | Deferred until deterministic edit/remap semantics close in `SG-3`. |
| Shared-engine NIMM/AITAS widening | `no` | `yes` | Deferred to `Track C` and explicitly not a v1 blocker. |

## Interface and Boundary Rules

- Preserve existing public datum-store and audit-log contracts during the initial SQL swap.
- Treat adapter replacement as the first implementation target, not contract redesign.
- Add one explicit portal-authority boundary for grants, ownership posture, and tool-exposure metadata if the current runtime composition does not already expose one cleanly enough.
- Keep shell and runtime public behavior unchanged in v1. File and workbench-oriented surfaces remain first-class, and SQL must project back into the same outward shapes.
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
- keep filesystem adapters available as compatibility projections
- define rollback posture before any authority promotion

Phase exit:

- shadow-mode topology is documented and no public contract redesign is required to compare SQL and filesystem behavior

### Phase 3 — Parity and Rollback Readiness

Required comparisons:

- anthology and document reads
- audit append and read flows
- tool exposure posture
- grant and ownership posture

Required posture:

- filesystem adapters remain available as compatibility projections
- parity drift is tracked explicitly with owner and remediation path
- rollback path is documented before SQL becomes primary

Phase exit:

- representative SQL and filesystem paths compare cleanly enough to promote approved surfaces without losing rollback safety

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
- explicit non-goals for v1
- list of behaviors that remain tool-local until a later design approval
- dependency notes showing where directive-context work depends on `SG-2` and `SG-3`

Current defaults:

- do not treat current CTS-GIS tool-local mediation behavior as shared-engine canon
- do not redesign the shared shell around directive-context semantics in v1
- do not block SQL cutover on directive-context closure

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

## Risks

1. **Semantic leakage risk**
   - Mitigation: unresolved identity and mutation rules stay on explicit gates instead of being implied into v1.
2. **Contract drift risk**
   - Mitigation: preserve public datum-store and audit-log contracts during the initial SQL swap.
3. **Runtime posture regression risk**
   - Mitigation: keep FND capability default removal until DB-backed grants reproduce the same effective posture.
4. **YAML over-formalization risk**
   - Mitigation: keep Markdown authoritative and limit YAML to indexing, dependency, and evidence support.

## Exit Criteria

V1 operational SQL-backed core exit:

- approved v1 SQL surfaces are explicitly defined, shadowed, and promoted with rollback posture
- retained filesystem surfaces are explicitly documented rather than implicitly deferred
- outward shell and runtime behavior remains file and workbench-oriented
- hard-coded FND capability defaults are removed only after grant-derived parity is proven, or are explicitly deferred with rationale

Native MOS closure exit:

- `SG-1` through `SG-4` are closed
- compatibility retirement policy is published
- unresolved semantic claims no longer remain in the semantic gap register
