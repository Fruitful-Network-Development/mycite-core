# MOS SQL Core Master Plan and Cutover Program

## PROMPT
Help me externalize the staging for seeing out and planning the cut over deffined by the contents of [mos_sql_backed_core_declaration_draft.md](repo/mycite-core/docs/personal_notes/MOS/mos_sql_backed_core_declaration_draft.md) .
Also see [datum_logic_area_investigation_clarity.md](repo/mycite-core/docs/personal_notes/MOS/datum_logic_area_investigation_clarity.md) , [data_base_use_findings.md](repo/mycite-core/docs/personal_notes/MOS/data_base_use_findings.md) , [mos_novelty_definition.md](repo/mycite-core/docs/personal_notes/MOS/mos_novelty_definition.md) , and [mycelial_ontological_schema.md](repo/mycite-core/docs/personal_notes/MOS/mycelial_ontological_schema.md) .

I want to properly plan and have a hard, stable unification of logic deffined and planned.
Consider the contents, refferences and conceptual materializations that will fuel the creation go the master plan to be made in [master_plan_mos.md](repo/mycite-core/docs/plans/master_plan_mos.md) , as well as the other plan files and audit files.
Consider the use of yaml file workflow to increase the effectiveness of this master plan, although don't be too strict with YAML as it can create dependeceies that don't allow for new aproaches to probelems or consideration that arrise.

---


## Planning and work

I’m grounding in the MOS docs first so we can turn the existing thinking into a cutover plan that’s actually stable and decision-complete. I’ll inspect the draft, the related investigation notes, and the current plan files before I ask you anything.


Explored 1 search, 1 list, ran 1 command
Listed files in docs
Searched for MOS|master_plan_mos|masterplan_mos|datum_logic_area_investigation_clarity|data_base_use_findings|mos_novelty_definition|mycelial_ontological_schema|mos_sql_backed_core_declaration_draft
Ran git -C /srv/repo/mycite-core status --short
I found two relevant files that aren’t tracked yet: the SQL-backed core declaration draft and master_plan_mos.md. Next I’m pulling the note set and current plan drafts into view so we can see what concepts are already stable versus still exploratory.


Explored 1 search, 1 list, ran 1 command
Listed files in docs
Searched for MOS|master_plan_mos|masterplan_mos|datum_logic_area_investigation_clarity|data_base_use_findings|mos_novelty_definition|mycelial_ontological_schema
Ran wc -l /srv/repo/mycite-core/docs/personal_notes/MOS/mos_sql_backed_core_declaration_draft.md /srv/repo/mycite-core/docs/personal_notes/MOS/datum_logic_area_investigation_clarity.md /srv/repo/mycite-core/docs/personal_notes/MOS/data_base_use_findings.md /srv/repo/mycite-core/docs/personal_notes/MOS/mos_novelty_definition.md /srv/repo/mycite-core/docs/personal_notes/MOS/mycelial_ontological_schema.md /srv/repo/mycite-core/docs/plans/master_plan_mos.md /srv/repo/mycite-core/docs/plans/masterplan_mos.md
The current master_plan_mos.md is empty, and there isn’t a separate masterplan_mos.md on disk, so the source of truth is going to come from the MOS notes themselves. I’m reading those now in full so we can separate declaration-level commitments from still-open investigation threads.


Explored 5 files, 1 search, 1 list
Read mos_sql_backed_core_declaration_draft.md
Read datum_logic_area_investigation_clarity.md
Read data_base_use_findings.md
Read mos_novelty_definition.md
Read mycelial_ontological_schema.md
Listed files in docs
Searched for /plans/|/audits/
I’ve got the main MOS note set in view now. The key pattern so far is that the declaration draft is already making firm v1 architectural commitments, while the other notes still contain open logic areas that need to be treated as gated dependencies rather than silently assumed solved.


Explored 4 files
Read README.md
Read peripheral_packages_modularization_report_2026-04-16.md
Read core_portal_datum_mss_protocol_report_2026-04-16.md
Read documentation_ia_audit_report_2026-04-20.md
I also found a repo-level documentation/YAML standardization effort already in progress. That’s useful here because it means the MOS master plan can lean on an existing “Markdown plan + optional structured YAML companion” pattern instead of inventing a one-off process.


Explored 4 files, 2 searches
Read agent_yaml_schema.md
Read agent_task_template_examples.md
Read documentation_ia_remediation_backlog.md
Read desktop_dm02_dm04_reconciliation_plan_2026-04-20.md
Searched for MOS\|Mycelial Ontological Schema\|hyphae\|canonical_v2\|MSS\|mycelial_ontological_schema in docs
Searched for datum_store\|portal grants\|tool exposure\|audit/event append store\|authoritative anthology\|reference resolution metadata in MyCiteV2
One more pass on repo truth: I’m checking the existing contract language for hyphae, plus the active CTS-GIS datum-handling audit plan, because those look like the strongest current anchors for what can be treated as already defined versus what must stay gated in the MOS rollout.


Explored 8 files
Read cts_gis_datum_handling_alignment_audit_plan_2026-04-20.md
Read portal_vocabulary_glossary.md
Read cts_gis_hops_profile_sources.md
Read contracts.py
Read samras_validity_and_mutation.md
Read samras_structural_model.md
Read cts_gis_samras_addressing.md
Read README.md
The main design fork is clear now: your notes support a strong v1 operational SQL core, but they do not support treating identity, hyphae, and generalized mutation semantics as already-closed canon. I want to lock three preferences before I turn this into a final master-plan structure, because each one changes how strict the staging and document split should be.


Asked 3 questions
What should the MOS master plan optimize for first?
The SQL‑backed core draft acknowledges that there is enough information to build a functional SQL authority adapter and datum store, but not enough for a complete native MOS standard because the missing pieces involve core identity and mutation semantics. Separate audits confirm that key algorithms—MSS hashing, hyphae derivation, deterministic edit rules and directive models—are undefined. The master plan should therefore optimise for delivering the v1 cut‑over while closing these semantic gaps in parallel. Use a single plan that runs the SQL migration and adapter work as its primary track but includes gated tasks to specify and implement the unresolved semantics. In short: build the operational SQL core now and place unresolved MOS semantics on an immediately adjacent track with explicit milestones rather than deferring them indefinitely.
How much authority should YAML have in the MOS planning workflow?
YAML should act as a companion index rather than a co‑equal authority. Keep the canonical plan, rationale and design decisions in Markdown and use YAML to record tasks, gates, dependencies and evidence links. This balances human readability with machine‑readability and avoids over‑formalising the planning process. The schema notes suggest YAML can optimise agent workflows but such configuration is optional; treating YAML as an index preserves flexibility.
How should NIMM/AITAS and broader directive-context ideas be handled in the master plan?
Handle NIMM/AITAS and other directive‑context ideas as a parallel design/spec track. These directive models are not part of the current core, so do not block the v1 SQL cut‑over on them. Instead, include a section in the master plan that outlines how directive‑context unification will be designed and integrated in a future phase. This keeps the core migration clean while ensuring the broader architecture will eventually absorb directive‑context logic.
I have the preferences locked now: one master program, v1 SQL cutover as the main line, unresolved semantics on an adjacent gated track, and YAML as a companion index rather than the authority. I’m doing one last repo pass on the actual port/adaptor seams so the staging I give you matches the code’s current cutover boundaries instead of staying purely conceptual.

Explored 6 files, 1 search, 3 lists
Listed files in ports
Searched for audit_log\|tool exposure\|capability\|grant\|peripheral in packages
Listed files in adapters
Read README.md
Read README.md
Read README.md
Read README.md
Read portal_shell_runtime.py
Listed files in plans
Read v2-authority_stack.md

---


## PLAN

### Summary

- Make [master_plan_mos.md](/srv/repo/mycite-core/docs/plans/master_plan_mos.md) the single authoritative MOS program document.
- Treat the program as **one plan with three tracks**:
  - `Track A`: v1 operational SQL-backed core cutover
  - `Track B`: adjacent semantic-closure gates for unresolved MOS rules
  - `Track C`: parallel directive-context design/spec track for future NIMM/AITAS widening
- Declare up front that v1 is allowed to become an **operational SQL authority** before MOS is a fully closed native standard.
- Add one companion YAML index at `docs/plans/master_plan_mos.index.yaml`; Markdown remains authoritative, YAML is only for task/gate/dependency/evidence indexing.

### Key Changes

- Start the master plan with a **logic authority matrix** that classifies every major rule as `canonical`, `operational_v1`, `compatibility_only`, or `unresolved`.
- Use current repo truth as the decision rule for v1: if personal notes conflict with active contracts/code, the repo wins for operational cutover and the conflict is logged into the semantic backlog instead of being silently unified.
- Explicitly mark the following as **stable enough for v1 cutover**:
  - portal instance as the authority principal
  - file-owned units remaining first-class in the API
  - ordered `layer-value_group-iteration` datum rows
  - adapter-swap architecture over rewrite
  - datum-store read surfaces, audit append/read seams, and tool-exposure/runtime composition as the main cutover boundaries
- Explicitly mark the following as **not closed canon yet**:
  - `version_hash` / MSS hashing semantics
  - generalized hyphae-chain derivation
  - generalized insertion/deletion remap algorithm
  - shared-engine NIMM/AITAS directive semantics
- In `Track A`, stage the cutover in this order:
  - `Phase 0`: consolidate source evidence and publish the authority matrix, semantic gap register, and cutover scope table
  - `Phase 1`: define the v1 SQL authority surface only for anthology/document reads, contract/reference-resolution metadata, audit/event append, portal grants, and tool exposure/config metadata
  - `Phase 2`: design shadow-mode SQL adapters behind existing seams while keeping file-shaped runtime contracts unchanged
  - `Phase 3`: run parity and rollback-readiness gates with filesystem adapters retained as compatibility projections
  - `Phase 4`: promote SQL to primary authority for the approved v1 surfaces
  - `Phase 5`: remove hard-coded FND capability defaults only after DB-backed grants produce the same effective posture
- In `Track A`, keep non-datum private filesystem assets out of the first cutover unless they already have stable adapter seams.
- In `Track A`, keep v1 write scope **narrowed** until semantic edit/remap rules are closed; read authority and controlled preview/apply behavior can move first, arbitrary generalized mutation cannot.
- In `Track B`, add four named gates that must be closed before claiming native MOS closure:
  - `SG-1`: version identity and MSS hashing policy
  - `SG-2`: hyphae derivation and stable semantic identity policy
  - `SG-3`: deterministic edit/remap algorithm for insert/delete/move
  - `SG-4`: standard-closure declaration criteria and compatibility retirement rules
- In `Track C`, keep NIMM/AITAS out of the v1 blocker path but require a design section describing future insertion points, non-goals, and what must remain tool-local until later.
- Use the existing YAML standard in [agent_yaml_schema.md](/srv/repo/mycite-core/docs/standards/agent_yaml_schema.md) as a baseline, but keep the MOS companion index lightweight:
  - required fields: `track`, `phase`, `status`, `dependencies`, `gates`, `evidence_refs`
  - optional freeform fields: `notes`, `open_questions`, `rationale`
  - rule: if Markdown and YAML disagree, Markdown wins

### Interfaces

- Preserve existing public datum-store and audit-log contracts during initial SQL swap; the first implementation target is adapter replacement, not contract redesign.
- Add one explicit portal-authority boundary for grants, ownership posture, and tool-exposure metadata if current runtime composition lacks a clean reusable seam.
- Keep shell/runtime public behavior unchanged in v1: file/workbench-oriented surfaces remain first-class, and SQL must project back into the same outward shapes.
- Use the active CTS-GIS datum-handling audit plan at [cts_gis_datum_handling_alignment_audit_plan_2026-04-20.md](/srv/repo/mycite-core/docs/audits/cts_gis_datum_handling_alignment_audit_plan_2026-04-20.md) as the main operational dependency for ordering, MSS-compatibility, hyphae/address semantics, and projection parity evidence.

### Test Plan

- The master plan is complete only when every major MOS claim is mapped to one of: `stable now`, `provisional for v1`, `compatibility only`, or `unresolved`.
- The cutover scope is complete only when every v1 SQL-owned surface and every explicit filesystem-retained surface is listed with a reason.
- Shadow-mode readiness is complete only when SQL and filesystem paths are compared on representative anthology/document reads, audit append/read flows, tool exposure posture, and grant posture.
- The plan fails if any milestone assumes MSS hashing, hyphae derivation, or generalized edit/remap semantics are already solved without closing the corresponding semantic gate.
- The YAML workflow is acceptable only if it validates link/dependency integrity while still allowing unstructured notes and new exploratory tasks without schema churn.
- Native MOS closure cannot be declared until `SG-1` through `SG-4` are closed; v1 SQL cutover may proceed earlier if outward contracts and rollback posture are proven.

### Assumptions and Defaults

- Default database posture: PostgreSQL-class relational authority, but the plan should stay adapter- and contract-oriented rather than vendor-specific.
- Default program posture: one master Markdown plan, not multiple competing master docs.
- Default naming posture: current MOS notes remain source evidence; once promoted, the master plan becomes the normative planning authority.
- Default declaration posture: if semantic gaps remain open, the release is named and communicated as a **v1 operational SQL-backed core**, not as a fully closed MOS standard.
- Default directive posture: NIMM/AITAS stays on a parallel design/spec track and does not block the core cutover.

---


## REVIEW

Review of MOS Master Plan:

The uploaded document lays out a coherent programme for migrating to a SQL-backed core while acknowledging that many MOS semantics remain unresolved. It proposes treating “master_plan_mos.md” as the single authoritative document, organised into three tracks: v1 SQL cutover, semantic-closure gating tasks, and a parallel design/spec track for future NIMM/AITAS work. The plan emphasises that v1 should focus on operational SQL authority (anthology and document reads, contracts and grants, audit append, tool exposure) without assuming problems like MSS hashing, hyphae derivation or deterministic edit logic have been solved. A companion YAML index is recommended for task tracking, but Markdown remains the canonical source. Overall, the plan provides a structured path to begin the SQL migration while keeping open issues clearly gated, and it aligns with the earlier guidance to externalize planning details and avoid conflating cutover with full MOS closure.

---
