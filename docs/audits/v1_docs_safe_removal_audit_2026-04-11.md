# V1 docs (`docs/V1/`) safe-removal audit

**Date:** 2026-04-11  
**Authority:** [plans/authority_stack.md](../plans/authority_stack.md), [ontology/non_authoritative_zones.md](../ontology/non_authoritative_zones.md)  
**Scope:** Every file under [docs/V1/](../V1/) (~90 paths), compared to authoritative V2 docs under [docs/](../README.md) and code under `MyCiteV2/packages/`.

## Executive summary

| Bucket | Count (approx.) | Guidance |
|--------|-----------------|----------|
| **Must-keep** | ~12 | Named on [v1_retention_vs_recreation.md](../plans/v1-migration/v1_retention_vs_recreation.md), sole copy of concepts not yet fully captured in ontology/ADRs, or still the best operational spec for live V2 seams (e.g. AWS CSM field semantics). |
| **Migrate-first, then delete** | ~55 | Wiki and modularity narrative overlaps V2 ontology, contracts, and package READMEs but retains product-specific or filesystem nuance; port unique bullets into `docs/wiki/`, ADRs, or port READMEs before removal. |
| **Delete-safe (evidence / duplicate)** | ~8 | Redundant copies under `docs/V1/archive/` where the same intent exists in V2 rollout docs or `docs/archive/`; stale todo notes superseded by tasks. |
| **Keep as non-authoritative reference** | ~15 | Historical lineage, glossary, governance notes—safe to trim later but low risk if left under `docs/V1/wiki/` until `docs/wiki/` gains equivalents. |

**Do not bulk-delete `docs/V1/`:** `MyCiteV1/docs/` is absent in this checkout; this tree is often the **only** local copy. [v1-migration/source_authority_index.md](../plans/v1-migration/source_authority_index.md) and phase docs now link here via `../V1/...` (see link-hygiene pass below).

## V2 canonical map (where truth lives)

| Concern | Authoritative V2 surface |
|---------|---------------------------|
| Module boundaries, dependency direction | [ontology/structural_invariants.md](../ontology/structural_invariants.md), [ontology/dependency_direction.md](../ontology/dependency_direction.md), [ontology/interface_surfaces.md](../ontology/interface_surfaces.md) |
| Settled choices | [decisions/](../decisions/) |
| Build order, migration | [plans/phases/](../plans/phases/), [plans/v1-migration/](../plans/v1-migration/) |
| Import/surface rules | [contracts/import_rules.md](../contracts/import_rules.md), [contracts/module_contract_template.md](../contracts/module_contract_template.md), [contracts/shell_region_kinds.md](../contracts/shell_region_kinds.md) |
| Enforcement templates | [testing/](../testing/) |
| Package-local contracts | `MyCiteV2/packages/**/README.md`, `**/contracts.py` |

Non-authoritative notes belong in [docs/wiki/](../wiki/) per [ontology/non_authoritative_zones.md](../ontology/non_authoritative_zones.md)—**not** in `docs/V1/` long term once content is migrated.

## Code anchor: `docs/V1/modularity/contracts/*.md` → MyCiteV2

| V1 contract | MyCiteV2 anchor (primary) | Gap / note | Recommended action |
|-------------|---------------------------|------------|-------------------|
| [contracts/state_machine.md](../V1/modularity/contracts/state_machine.md) | `MyCiteV2/packages/state_machine/`, [state_machine/README.md](../../MyCiteV2/packages/state_machine/README.md), [hanus_shell/README.md](../../MyCiteV2/packages/state_machine/hanus_shell/README.md) | V1 names `mycite_core/state_machine`; behavior is recreated in V2. | **Migrate-first:** ensure any unique reducer/AITAS rules not in READMEs are in phase 03 outputs or ontology; then archive V1 file. |
| [contracts/shell.md](../V1/modularity/contracts/shell.md) | [ports/shell_surface/](../../MyCiteV2/packages/ports/shell_surface/), [hanus_shell/](../../MyCiteV2/packages/state_machine/hanus_shell/) | — | **Migrate-first** → **delete** when shell_region + phase 03 docs subsume UI region detail. |
| [contracts/sandboxes.md](../V1/modularity/contracts/sandboxes.md) | `MyCiteV2/packages/sandboxes/*`, [sandboxes/README.md](../../MyCiteV2/packages/sandboxes/README.md) | — | **Migrate-first** (or cite in ADR) then **delete**. |
| [contracts/tools_shared.md](../V1/modularity/contracts/tools_shared.md) | [tools/README.md](../../MyCiteV2/packages/tools/README.md), [tools/_shared/README.md](../../MyCiteV2/packages/tools/_shared/README.md), [tools/allowed_dependencies.md](../../MyCiteV2/packages/tools/allowed_dependencies.md) | — | **Migrate-first** then **delete**. |
| [contracts/data_engine.md](../V1/modularity/contracts/data_engine.md) | [ports/datum_store/](../../MyCiteV2/packages/ports/datum_store/), [core/mss/](../../MyCiteV2/packages/core/mss/), [adapters/filesystem/live_system_datum_store.py](../../MyCiteV2/packages/adapters/filesystem/live_system_datum_store.py) | V1 “data engine” split across ports + adapters. | **Migrate-first** (datum authority wording) then **delete**. |
| [contracts/contracts.md](../V1/modularity/contracts/contracts.md) (domain) | [modules/domains/contracts/](../../MyCiteV2/packages/modules/domains/contracts/) | — | **Migrate-first** then **delete**. |
| [contracts/vault.md](../V1/modularity/contracts/vault.md) | [ports/session_keys/](../../MyCiteV2/packages/ports/session_keys/), [adapters/session_vault/](../../MyCiteV2/packages/adapters/session_vault/), [core/crypto/](../../MyCiteV2/packages/core/crypto/) | Matches v2 split of `vault_session`. | **Migrate-first** then **delete**. |
| [contracts/aws_csm.md](../V1/modularity/contracts/aws_csm.md) | [modules/cross_domain/aws_csm_onboarding/](../../MyCiteV2/packages/modules/cross_domain/aws_csm_onboarding/), [ports/aws_csm_onboarding/](../../MyCiteV2/packages/ports/aws_csm_onboarding/), [adapters/filesystem/live_aws_profile.py](../../MyCiteV2/packages/adapters/filesystem/live_aws_profile.py) | **Field-level semantics** for mailbox profiles still documented best here; cited by tasks/reports. | **Keep** until a V2 contract doc or port README inlines the same schema rules; then **delete**. |
| [contracts/paypal_csm.md](../V1/modularity/contracts/paypal_csm.md) | No `MyCiteV2` package (names appear only in [tests/architecture/test_runtime_composition_boundaries.py](../../MyCiteV2/tests/architecture/test_runtime_composition_boundaries.py) as boundary tokens) | V2 stub / future seam. | **Keep** (nearest spec) or **migrate-first** into a short ADR when PayPal work starts. |
| [contracts/keycloak_sso.md](../V1/modularity/contracts/keycloak_sso.md) | Same as PayPal—test token only | No V2 implementation doc. | **Keep** or **migrate-first** to ADR. |
| [contracts/profiles.md](../V1/modularity/contracts/profiles.md) | Live profile handling in filesystem adapters + onboarding | Overlaps runtime config docs in wiki. | **Migrate-first** then **delete**. |
| [contracts/operations.md](../V1/modularity/contracts/operations.md) | Cross-domain ops modules (AWS read/narrow write, audit) | Map per concern to `modules/cross_domain/*`. | **Migrate-first** then **delete**. |
| [contracts/analytics.md](../V1/modularity/contracts/analytics.md) | [adapters/filesystem/analytics_event_paths.py](../../MyCiteV2/packages/adapters/filesystem/analytics_event_paths.py) | Thin; may be README-only in V2. | **Migrate-first** then **delete**. |
| [contracts/composition.md](../V1/modularity/contracts/composition.md) | `MyCiteV2/instances/_shared/runtime/`, [adapters/portal_runtime/](../../MyCiteV2/packages/adapters/portal_runtime/) | Host composition only. | **Migrate-first** then **delete**. |

### Other modularity files

| Path | V2 anchor | Action |
|------|-----------|--------|
| [modularity/module_contracts.md](../V1/modularity/module_contracts.md) | [mycite_v2_structure_report.md](../plans/v1-migration/mycite_v2_structure_report.md), ontology | **Migrate-first** (table is V1 path vocabulary) → **delete** when drift ledger no longer needs citations. |
| [modularity/module_inventory.md](../V1/modularity/module_inventory.md) | [v1_audit_map.md](../plans/v1-migration/v1_audit_map.md) | Same. |
| [modularity/module_map.json](../V1/modularity/module_map.json) | Historical JSON for V1 paths | **Keep** as evidence or move to `docs/plans/v1-migration/historical/` → optional **delete** from `V1/`. |
| [modularity/compatibility_seams.md](../V1/modularity/compatibility_seams.md) | [plans/post_mvp_rollout/](../plans/post_mvp_rollout/) bridge docs | **Migrate-first** unique seams → rollout doc; then **delete**. |
| [modularity/runtime_alignment_report.md](../V1/modularity/runtime_alignment_report.md) | Runtime composition in phase docs + `adapters/portal_runtime` | **Migrate-first** → **delete**. |
| [modularity/tool_development_guide.md](../V1/modularity/tool_development_guide.md) | [ontology/interface_surfaces.md](../ontology/interface_surfaces.md), [07_tools.md](../plans/phases/07_tools.md), `packages/tools/*` | Overlaps [tool_dev.md](../V1/plans/tool_dev.md). | **Merge** into wiki or extend `packages/tools` docs; then **delete**. |

## Plans (`docs/V1/plans/`)

| File | Classification | Notes |
|------|------------------|-------|
| [hanus_interface_model.md](../V1/plans/hanus_interface_model.md) | **Must-keep** | [v1_retention_vs_recreation.md](../plans/v1-migration/v1_retention_vs_recreation.md) “retain as concept.” |
| [tool_dev.md](../V1/plans/tool_dev.md) | **Must-keep** | Same; tool authority and path roots. |
| [tool_alignment.md](../V1/plans/tool_alignment.md) | **Keep** until phase 07 + tool READMEs absorb alignment rules | Supporting authority in source index. |
| [news_letter_workflow_correction.md](../V1/plans/news_letter_workflow_correction.md) | **Migrate-first** or **delete** | Product/process; move to `docs/wiki/` or task context if still needed. |

## Root

| File | Classification | Notes |
|------|------------------|-------|
| [ownership-boundary.md](../V1/ownership-boundary.md) | **Migrate-first** | V1 “mycite-core owns portal semantics” statement; V2 uses ontology + host rules—capture any unique ops boundaries in wiki/ADR before removal. |

## Wiki (`docs/V1/wiki/**`)

Bulk policy: wiki pages are **secondary** relative to V2 ontology (per [non_authoritative_zones.md](../ontology/non_authoritative_zones.md)). They are **not** “superseded” in the sense of delete-safe unless a V2 or `docs/wiki/` document replaces their *unique* claims.

| Area | Representative paths | V2 / code overlap | Action |
|------|---------------------|-------------------|--------|
| **Architecture** | `wiki/architecture/*.md`, `system-state-machine.md` | [interface_surfaces.md](../ontology/interface_surfaces.md), `packages/state_machine/*` | **Migrate-first** (glossary + diagrams), then trim. |
| **AITAS / shell** | `aitas-context.md`, `shell-and-page-composition.md` | `state_machine/aitas`, `hanus_shell` | Same. |
| **Data model** | `wiki/data-model/*.md` | [core/mss/README.md](../../MyCiteV2/packages/core/mss/README.md), [datum_refs](../../MyCiteV2/packages/core/datum_refs/), ontology datum rules | **Migrate-first** operational nuance (write pipeline, mediation defaults). |
| **MSS contracts** | `wiki/contracts-mss/*.md` | `core/mss`, port contracts | **Migrate-first** then delete per file after review. |
| **SAMRAS / HOPS** | `wiki/samras/*`, `wiki/hops/homogeneous_ordinal_partition_structure.md` | [core/structures/samras](../../MyCiteV2/packages/core/structures/samras/), [core/structures/hops](../../MyCiteV2/packages/core/structures/hops/), [ports/time_projection](../../MyCiteV2/packages/ports/time_projection/) | **HOPS doc: must-keep** per retention list until ontology/phase doc cites it. |
| **Sandbox / network / runtime-build** | `wiki/sandbox-resources/*`, `wiki/network-hosted/*`, `wiki/runtime-build/*` | `packages/sandboxes`, `adapters/portal_runtime`, phase plans | **Migrate-first** deployment nuance. |
| **Tools** | `wiki/tools/*.md` (agro-erp, time-address, internal sources, etc.) | Tool packages + [07_tools.md](../plans/phases/07_tools.md) | **Migrate-first** product-specific mediation; **delete** only after parity. |
| **Governance** | `wiki/governance/*.md` | [decisions/](../decisions/), repo README | Low risk to **keep** or move to `docs/wiki/governance/`. |
| **Navigation** | `Home.md`, `Glossary.md`, `wiki/**/README.md` | — | **Keep** while `docs/V1/wiki` remains; if tree removed, recreate stubs under `docs/wiki/`. |
| **Todo** | `wiki/todo/*.md` | Tasks / rollout | **Delete-safe** after confirming issues closed (verify against `tasks/`). |
| **Misc** | `portal_sandbox_context_recovery.md`, `docker-vs-native-runtime-context-report.md` | Ops reports | **Migrate-first** to `docs/audits/` or `docs/wiki/` then **delete** from V1. |

## `docs/V1/archive/**`

| Path | Relationship to V2 | Action |
|------|--------------------|--------|
| Newsletter / inbound / AWS CMS plans | Partial overlap with [plans/post_mvp_rollout/](../plans/post_mvp_rollout/) and `docs/archive/*` (different numbering scheme—not byte duplicates) | **Keep** until rollout docs explicitly subsume; then **delete** or move to `docs/archive/`. |
| [archive/agent_prompts/hard_refactor_repo_prompt.md](../V1/archive/agent_prompts/hard_refactor_repo_prompt.md) | Non-authoritative | **Delete-safe** if not referenced. |
| [archive/audits/portal_logic_boundies_audit.md](../V1/archive/audits/portal_logic_boundies_audit.md) | Contains **broken** absolute paths to old `docs/modularity/` layout | **Migrate** still-valid findings to `docs/audits/` or fix links to `../modularity/contracts/`; then **delete** or archive. |

## Reference scan (blockers)

| Pattern | Hits | Impact |
|---------|------|--------|
| `MyCiteV1/docs/...` | [README.md](../../README.md), [tasks/T-009*.yaml](../../tasks/T-009-investigate-v1-v2-aws-csm-onboarding-parity.yaml), [reports/T-009-investigation.md](../../reports/T-009-investigation.md) | Updated README + task to include **`docs/V1/...`** paths so agents find files without `MyCiteV1/docs/`. |
| `docs/V1` | (no prior hits) | Safe to treat `docs/V1/` as canonical mirror path in this repo. |
| GitHub URLs in `v1-migration/historical/*.md` | Old `docs/modularity/...` | Historical; optional follow-up to annotate “moved to docs/V1/”. |

## Ordered deletion waves (when executing)

1. **Wave A:** `docs/V1/wiki/todo/*`, obvious duplicate `archive/*` pairs (same content as `plans/*` where verified), agent prompts—**lowest risk**.
2. **Wave B:** `docs/V1/modularity/module_map.json` and reports superseded by v1-migration + ontology—**after** any unique bullets copied.
3. **Wave C:** `docs/V1/modularity/contracts/*.md` except **aws_csm**, **paypal_csm**, **keycloak_sso**—**after** port README / contract checks pass.
4. **Wave D:** Remaining wiki pages **per subtree** after `docs/wiki/` counterparts exist.
5. **Never wave:** [hanus_interface_model.md](../V1/plans/hanus_interface_model.md), [tool_dev.md](../V1/plans/tool_dev.md), [homogeneous_ordinal_partition_structure.md](../V1/wiki/hops/homogeneous_ordinal_partition_structure.md), [aws_csm.md](../V1/modularity/contracts/aws_csm.md) until V2 replacements are explicit.

## V2 code surfaces with thin docs (gaps)

These packages exist in **MyCiteV2** but rely more on code than on top-level V2 markdown; migrating V1 wiki bullets here reduces need for `docs/V1/`:

- `packages/modules/cross_domain/aws_csm_onboarding/` — add schema doc or extend README from V1 `aws_csm.md`.
- `packages/adapters/portal_runtime/` — composition edge cases from V1 `composition.md` + runtime wiki.
- `packages/ports/time_projection/` + `core/structures/hops/` — cite HOPS doc or inline minimal spec.

## Link hygiene (completed in repo)

The following now use **`../V1/`** from `docs/plans/*` instead of broken `../../../../docs/...` paths: [source_authority_index.md](../plans/v1-migration/source_authority_index.md), [v1_retention_vs_recreation.md](../plans/v1-migration/v1_retention_vs_recreation.md), [v1_drift_ledger.md](../plans/v1-migration/v1_drift_ledger.md), [hanus_interface_analysis.md](../plans/v1-migration/hanus_interface_analysis.md), [phases/03_state_machine_and_hanus_shell.md](../plans/phases/03_state_machine_and_hanus_shell.md), [phases/07_tools.md](../plans/phases/07_tools.md), [authority_stack.md](../plans/authority_stack.md) (item 5 clarified). Evidence paths in `source_authority_index.md` now prefix **`MyCiteV1/`** where V1 code lives.

---

## Per-file checklist (`docs/V1/`)

Legend: **K** = keep, **M** = migrate-first then delete, **D** = delete-safe when preconditions met, **R** = retention list / task-blocked.

| Path | K/M/D/R |
|------|---------|
| ownership-boundary.md | M |
| plans/hanus_interface_model.md | R |
| plans/tool_dev.md | R |
| plans/tool_alignment.md | K |
| plans/news_letter_workflow_correction.md | M |
| modularity/tool_development_guide.md | M |
| modularity/module_contracts.md | M |
| modularity/module_inventory.md | M |
| modularity/module_map.json | D |
| modularity/compatibility_seams.md | M |
| modularity/runtime_alignment_report.md | M |
| modularity/contracts/analytics.md | M |
| modularity/contracts/aws_csm.md | R |
| modularity/contracts/composition.md | M |
| modularity/contracts/contracts.md | M |
| modularity/contracts/data_engine.md | M |
| modularity/contracts/keycloak_sso.md | K |
| modularity/contracts/operations.md | M |
| modularity/contracts/paypal_csm.md | K |
| modularity/contracts/profiles.md | M |
| modularity/contracts/sandboxes.md | M |
| modularity/contracts/shell.md | M |
| modularity/contracts/state_machine.md | M |
| modularity/contracts/tools_shared.md | M |
| modularity/contracts/vault.md | M |
| wiki/Home.md | K |
| wiki/Glossary.md | K |
| wiki/README.md | K |
| wiki/portal_sandbox_context_recovery.md | M |
| wiki/docker-vs-native-runtime-context-report.md | M |
| wiki/architecture/*.md (8 files) | M |
| wiki/data-model/*.md (9 files) | M |
| wiki/contracts-mss/*.md (6 files) | M |
| wiki/governance/*.md (4 files) | K/M |
| wiki/hops/homogeneous_ordinal_partition_structure.md | R |
| wiki/network-hosted/*.md (6 files) | M |
| wiki/runtime-build/*.md (3 files) | M |
| wiki/samras/*.md (4 files) | M |
| wiki/sandbox-resources/*.md (4 files) | M |
| wiki/tools/*.md (10 files) | M |
| wiki/todo/*.md (2 files) | D |
| wiki/archive/*.md (2 files) | M |
| archive/*.md (8 files) | M/D |
| archive/agent_prompts/*.md (1 file) | D |
| archive/audits/*.md (1 file) | M |

_Counts align with ~90 paths; README index files in wiki subtrees follow the same **M** default as siblings unless listed._
