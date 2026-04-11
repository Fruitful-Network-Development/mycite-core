# Legacy Docs Truth Audit

**Date:** 2026-04-11  
**Scope:** `docs/plans/legacy/`, `docs/contracts/legacy/`, `docs/wiki/legacy/`  
**Primary comparison authority:** `docs/README.md`, `docs/plans/v2-authority_stack.md`, `docs/ontology/non_authoritative_zones.md`

This audit implements a section-based legacy review. It does **not** move files, fix links, or reconcile the active `docs/archive/V1/` to `legacy/` rename. Naming drift such as `V1/` vs `legacy/` and `v1-migration/` vs `version-migration/` is treated here as evidence of documentation drift, not as implementation work.

## Review Contract

Each section includes:

- a short statement of what the section was meant to own and whether that still makes sense
- a per-file ledger with `path`, `purpose`, `authority_class`, `truth_status`, `recommended_action`, `reason`, and `comparison_sources`
- an explicit section recommendation

Allowed labels used below:

- `authority_class`: `v2_authority`, `legacy_reference`, `historical_evidence`, `stale_conflict`, `placeholder_or_orphan`
- `truth_status`: `accurate_for_v2`, `accurate_for_v1_only`, `mixed`, `superseded`, `unclear`
- `recommended_action`: `keep_as_current`, `retain_as_legacy_reference`, `promote_unique_concepts`, `archive_only`, `delete_candidate`

## Comparison Shorthand

| shorthand | source |
| --- | --- |
| `root` | `docs/README.md` |
| `auth` | `docs/plans/v2-authority_stack.md` |
| `naz` | `docs/ontology/non_authoritative_zones.md` |
| `inv` | `docs/ontology/structural_invariants.md` |
| `iface` | `docs/ontology/interface_surfaces.md` |
| `wikiR` | `docs/wiki/README.md` |
| `ph03` | `docs/plans/phases/03_state_machine_and_hanus_shell.md` |
| `ph07` | `docs/plans/phases/07_tools.md` |
| `ph09` | `docs/plans/phases/09_runtime_composition.md` |
| `ret` | `docs/plans/version-migration/v1_retention_vs_recreation.md` |
| `sai` | `docs/plans/version-migration/source_authority_index.md` |
| `adr4` | `docs/decisions/decision_record_0004_tools_attach_through_shell_surfaces.md` |
| `adr7` | `docs/decisions/decision_record_0007_hosts_compose_but_do_not_own_domain_logic.md` |
| `shellKinds` | `docs/contracts/shell_region_kinds.md` |
| `awsFirst` | `docs/plans/post_mvp_rollout/admin_first/aws_first_surface.md` |
| `band3` | `docs/plans/post_mvp_rollout/slice_registry/admin_band3_aws_csm_sandbox_surface.md` |
| `band4` | `docs/plans/post_mvp_rollout/slice_registry/admin_band4_aws_csm_onboarding_surface.md` |

## Rollup

- **Current V2 authority:** none of the reviewed files. Every file in scope is subordinate to current v2 docs by location and by current authority rules.
- **Retained legacy reference:** AWS-CMS mailbox and inbound planning, `v1-hanus_interface_model.md`, `v1-tool_dev.md`, `contracts/legacy/aws_csm.md`, `wiki/legacy/architecture/system-state-machine.md`, `wiki/legacy/samras/*`, `wiki/legacy/hops/*`, and several network/MSS/tool concept pages.
- **Historical evidence:** prompt/output transcripts, staging ledgers, recovery notes, infrastructure reports, and explicitly superseded newsletter variants.
- **Cleanup candidates:** stale governance pages that still claim `docs/wiki/` is primary authority, obsolete path-inventory pages, and duplicate superseded newsletter notes after unique rules are harvested.

---

## 1. `docs/plans/legacy/modularity/` except `AWS-CSM/`

This section was meant to freeze the post-hard-cut V1 ownership map: seams, owners, tool state rules, and runtime alignment. That purpose still makes sense as migration evidence, but the section is not current v2 authority because it uses old package names and a V1 ownership model that v2 deliberately split into ontology, ADRs, phases, ports, and adapters.

Conflicts with current v2 authority:

- it still treats old package/layout vocabulary as canonical
- it describes wrapper and runtime owners through V1 shapes instead of v2 inward-layer composition
- it encodes legacy tool package structure directly rather than the v2 `packages/*` split

Unique concepts worth preserving:

- explicit seam retirement conditions
- runtime state vs authoring-surface separation
- tool utility-state vs datum-authority separation

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/plans/legacy/modularity/compatibility_seams.md` | Lists tolerated wrapper seams and retirement triggers. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | Useful V1 seam map, but every owner and path is pre-v2 and superseded by host-composition rules. | `auth, adr7, ph09` |
| `docs/plans/legacy/modularity/module_contracts.md` | Maps V1 module homes, ownership, and dependencies. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | Strong migration evidence for old boundaries, but it preserves V1 package vocabulary rather than v2 structure. | `auth, inv, sai` |
| `docs/plans/legacy/modularity/module_inventory.md` | Inventory of V1 runtime, state-machine, tools, and instance areas. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | Still useful as a migration inventory, but it is a V1 path map, not a v2 architecture surface. | `auth, ph09, sai` |
| `docs/plans/legacy/modularity/module_map.json` | Machine-readable snapshot of the V1 module map. | `historical_evidence` | `accurate_for_v1_only` | `archive_only` | Evidence artifact only; the JSON mirrors the old structure and has no v2 governance role. | `auth, sai` |
| `docs/plans/legacy/modularity/ownership-boundary.md` | States what `mycite-core` owns vs what host/runtime owns. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The repo-vs-host boundary still matters, but the doc speaks in V1 portal terms and should not remain the active boundary definition. | `root, inv, adr7` |
| `docs/plans/legacy/modularity/runtime_alignment_report.md` | Snapshot of where runtime responsibilities were aligned after the hard cut. | `historical_evidence` | `accurate_for_v1_only` | `archive_only` | Useful as a migration checkpoint, but it is a dated alignment report for the old runtime shape. | `auth, adr7, ph09` |
| `docs/plans/legacy/modularity/tool_development_guide.md` | Prescriptive guide for adding tools without recreating drift. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Its state-authority rules still matter, but the package layout and path contract are V1-shaped. | `iface, ph07, adr4, ret` |

Section recommendation: `partially harvest`

---

## 2. `docs/plans/legacy/modularity/AWS-CSM/`

This section was meant to capture AWS-CMS onboarding, inbox, and newsletter corrections during late V1 operations. Unlike most legacy planning, it still carries unique mailbox semantics that current v2 rollout docs only summarize at a higher level.

Conflicts with current v2 authority:

- control-plane examples use V1 route shapes
- utility-file locations and UI assumptions are V1 runtime details
- newsletter documents mix active correction rules with clearly superseded alternatives

Unique concepts worth preserving:

- mailbox profile as the canonical operational unit
- staged vs initiated mailbox lifecycle
- inbound/receive-path state as a first-class mailbox concern

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/plans/legacy/modularity/AWS-CSM/v1-aws_cms_mailbox_profile_refactor_plan.md` | Refactors AWS-CMS from domain profiles to mailbox profiles. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Still the richest mailbox-profile semantics document, but it is coupled to V1 routes, UI surfaces, and control-plane language. | `auth, awsFirst, band4, naz` |
| `docs/plans/legacy/modularity/AWS-CSM/v1-inbound_replacement_and_legacy_forwarder_retirement_plan.md` | Plans replacement of the legacy inbound forwarding chain. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The inbound-as-mailbox-concern idea still matters, but the execution model is V1 operational planning rather than current v2 policy. | `auth, band4, awsFirst` |
| `docs/plans/legacy/modularity/AWS-CSM/v1-news_letter_workflow_correction.md` | Records the implemented V1 newsletter workflow correction. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | Marked implemented, but it still captures active V1 newsletter rules that later AWS slices may need as evidence. | `auth, awsFirst, naz` |
| `docs/plans/legacy/modularity/AWS-CSM/v1-newsletter_separate_tool_context.md` | Proposes newsletter as a separate service-tool lane. | `historical_evidence` | `superseded` | `archive_only` | The file says it is superseded and conflicts with the later corrected AWS-CMS/newsletter posture. | `auth, awsFirst, naz` |
| `docs/plans/legacy/modularity/AWS-CSM/v1-newsletter_subscriber_store_and_lambda_delivery_plan.md` | Describes a future separate newsletter system. | `historical_evidence` | `superseded` | `archive_only` | Useful lineage for a deferred design, but not current truth for either V1 operations or v2 rollout. | `auth, awsFirst, naz` |

Section recommendation: `keep as reference`

---

## 3. `docs/plans/legacy/v1-*`

This group mixes retained conceptual sources with pure implementation transcript material. The section still matters because current version-migration docs explicitly point at some of these files as concept sources.

Conflicts with current v2 authority:

- some files are prompt/output transcripts rather than stable docs
- some still point at old locations like `docs/plans/tool_dev.md`
- only a subset are explicitly retained by current version-migration docs

Unique concepts worth preserving:

- Hanus/AITAS attention and directive modeling
- tool datum-authority rules

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/plans/legacy/v1-hanus_interface_model.md` | Concept record for the Hanus interface model. | `legacy_reference` | `mixed` | `retain_as_legacy_reference` | Current migration docs explicitly retain this as a concept source, even though the file is a prompt-derived conceptual record rather than a clean v2 spec. | `auth, ph03, ret, sai` |
| `docs/plans/legacy/v1-news_letter_workflow_correction.md` | Concise binding-decision version of the newsletter correction. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | Still useful for V1 newsletter behavior, but it is not part of current v2 authority and overlaps the AWS-CSM correction docs. | `auth, awsFirst, naz` |
| `docs/plans/legacy/v1-tool_alignment.md` | Prompt/output transcript describing past alignment work. | `stale_conflict` | `superseded` | `archive_only` | It is a transcript, not a durable contract, and it refers to stale paths and now-rejected governance assumptions. | `auth, wikiR, ph07` |
| `docs/plans/legacy/v1-tool_dev.md` | Primary tool doctrine for shell-first tool attachment and datum authority. | `legacy_reference` | `mixed` | `retain_as_legacy_reference` | Current migration docs still cite it as the primary legacy source for tool authority rules, even though the exact layout is V1-shaped. | `auth, ph07, adr4, ret, sai` |

Section recommendation: `keep as reference`

---

## 4. `docs/contracts/legacy/`

These files were meant to express compact ownership contracts for V1 modules and tools. Their format is still helpful, but the contracts describe V1 owners, V1 storage roots, and V1 split points rather than settled v2 interfaces.

Conflicts with current v2 authority:

- they encode V1 module names as if they were still canonical
- several contracts collapse concerns that v2 split across ports, adapters, and modules
- tool contracts assume V1 runtime/storage roots

Unique concepts worth preserving:

- shell/state-machine/tool boundary language
- AWS-CMS field and IAM semantics
- payload/cache and utility-vs-datum authority cues

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/contracts/legacy/analytics.md` | Compact V1 contract for the analytics tool. | `historical_evidence` | `accurate_for_v1_only` | `archive_only` | A narrow V1 tool contract with no current v2 equivalent or active authority role. | `auth, ph07, naz` |
| `docs/contracts/legacy/aws_csm.md` | Compact V1 contract for AWS-CMS behavior and IAM posture. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Still carries mailbox/IAM semantics not fully restated in v2 docs, but it is anchored to V1 tool storage and runtime language. | `auth, awsFirst, band4, naz` |
| `docs/contracts/legacy/composition.md` | Contract for runtime flavor loading and instance context composition. | `historical_evidence` | `accurate_for_v1_only` | `archive_only` | Useful as V1 runtime evidence, but current host-composition rules live elsewhere in v2. | `auth, adr7, ph09` |
| `docs/contracts/legacy/contracts.md` | Contract-line ownership summary for schemas, bindings, and receipts. | `legacy_reference` | `accurate_for_v1_only` | `promote_unique_concepts` | The concern still exists, but v2 intentionally reorganizes it and does not keep this V1 bucket as-is. | `auth, inv, ret` |
| `docs/contracts/legacy/data_engine.md` | Data-engine ownership and binary/cache authority summary. | `legacy_reference` | `mixed` | `promote_unique_concepts` | It contains useful datum/payload authority rules, but the V1 “data engine” bucket is not a valid v2 structure. | `auth, inv, naz` |
| `docs/contracts/legacy/keycloak_sso.md` | Compact V1 contract for the Keycloak SSO tool. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | No current v2 contract replaces it, so it remains a legacy spec placeholder rather than current authority. | `auth, ph07, naz` |
| `docs/contracts/legacy/operations.md` | Compact V1 contract for the operations tool. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | Useful only as legacy tool-surface evidence; there is no current v2 contract that supersedes it directly. | `auth, ph07, naz` |
| `docs/contracts/legacy/paypal_csm.md` | Compact V1 contract for the PayPal CSM tool. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | Still the clearest local spec for that future seam, but it remains fully V1-shaped. | `auth, ph07, naz` |
| `docs/contracts/legacy/profiles.md` | Contract for `config.json`, profile files, and profile context. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Repo-vs-state and profile-normalization ideas still matter, but the file bakes in V1 file names and boundaries. | `root, auth, ret` |
| `docs/contracts/legacy/sandboxes.md` | Contract for system and tool sandbox ownership. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The lifecycle/orchestration ideas align with v2, but the ownership language is still V1 runtime-specific. | `inv, iface, naz` |
| `docs/contracts/legacy/shell.md` | Contract for shell verbs, cards, and activation rules. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The shell-first doctrine survives, but the doc is still a V1 shell contract rather than a v2 state-machine surface. | `iface, ph03, adr4, shellKinds` |
| `docs/contracts/legacy/state_machine.md` | Contract for shell/workbench transitions and staged mutation rules. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Strong concept overlap with v2 phase 03, but still expressed through V1 module language. | `inv, iface, ph03` |
| `docs/contracts/legacy/tools_shared.md` | Contract for shared tool catalog and helpers. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The shared tool helper idea survives, but v2 packages and dependency rules are more specific than this V1 bucket. | `ph07, adr4, iface` |
| `docs/contracts/legacy/vault.md` | Contract for KeyPass, vault adapters, and vault inventory. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | V2 intentionally split this concern, so the V1 contract remains useful only as legacy evidence. | `inv, ret, auth` |

Section recommendation: `partially harvest`

---

## 5. `docs/wiki/legacy/` root files

These files were meant to be the landing surface for a concept-first wiki. Their high-level concepts still matter, but the section overclaims authority relative to the current v2 documentation model.

Conflicts with current v2 authority:

- `README.md` says `docs/wiki` is the primary maintained knowledge base
- `Home.md` presents the legacy wiki as the current application model
- report/recovery notes are mixed in beside concept docs

Unique concepts worth preserving:

- glossary terms around `SYSTEM`, `NIMM`, and `AITAS`
- any filesystem-canonicalization notes not already captured elsewhere

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/wiki/legacy/Glossary.md` | Defines shared portal terms such as `SYSTEM`, `NIMM`, and `AITAS`. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Several terms still matter conceptually, but the glossary is not current v2 authority and mixes V1 framing with retained concepts. | `root, wikiR, ph03, ret` |
| `docs/wiki/legacy/Home.md` | Navigation map for the legacy wiki. | `historical_evidence` | `superseded` | `archive_only` | Useful only as legacy navigation; it presents the legacy wiki as the current model. | `root, wikiR, naz` |
| `docs/wiki/legacy/README.md` | Explains the old wiki governance model. | `stale_conflict` | `superseded` | `archive_only` | It directly conflicts with current docs governance by claiming `docs/wiki/` is primary and by referencing retired roots like `docs/modularity/`. | `root, wikiR, naz, auth` |
| `docs/wiki/legacy/docker-vs-native-runtime-context-report.md` | Operational report on Docker vs native services. | `historical_evidence` | `unclear` | `archive_only` | Time-sensitive infrastructure report; useful for lineage, not for current v2 truth. | `root, naz` |
| `docs/wiki/legacy/portal_sandbox_context_recovery.md` | Recovery note for portal sandbox canonicalization work. | `historical_evidence` | `mixed` | `archive_only` | It preserves useful context, but it is a recovery note rather than a stable contract and is written entirely through the V1 portal filesystem model. | `root, inv, naz` |

Section recommendation: `archive`

---

## 6. `docs/wiki/legacy/architecture/`

This subtree was meant to explain the conceptual architecture of the portal: one `SYSTEM` workbench, shared shell regions, AITAS, and host-agnostic core logic. The concepts remain important, but the subtree is legacy reference because current v2 authority for these topics lives in ontology, ADRs, phase 03, and shell contracts.

Conflicts with current v2 authority:

- pages self-label as canonical even though the wiki is now explicitly non-authoritative
- some pages mix current conceptual rules with V1 runtime assumptions
- one page is an audit/risk register rather than a stable contract

Unique concepts worth preserving:

- `SYSTEM` as one reflective state machine
- AITAS vocabulary
- shell region and composition language

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/wiki/legacy/architecture/README.md` | Topic index for architecture concepts. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The topic framing is still useful, but the subtree cannot remain a canonical owner under current docs rules. | `root, wikiR, auth` |
| `docs/wiki/legacy/architecture/aitas-context.md` | Describes AITAS as the shared context payload vocabulary. | `legacy_reference` | `mixed` | `promote_unique_concepts` | AITAS remains a retained concept, but the page is not the authoritative v2 shell-state definition. | `ph03, ret, sai` |
| `docs/wiki/legacy/architecture/application-core-and-adapters.md` | Explains host-agnostic core logic and adapter-level routing. | `legacy_reference` | `mixed` | `promote_unique_concepts` | It aligns with inward-layer thinking, but it still describes the old portal architecture rather than the current v2 module stack. | `inv, adr7, ph09` |
| `docs/wiki/legacy/architecture/canonical-direction-gaps.md` | Tracks implementation-risk gaps and coupling drift. | `historical_evidence` | `unclear` | `archive_only` | Useful as a risk log for the old runtime, but not a durable contract or current truth source. | `auth, naz` |
| `docs/wiki/legacy/architecture/shell-and-page-composition.md` | Defines shell regions and foreground compositions. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The shell-region ideas still matter, but the page is a legacy contract and not the v2 shell surface owner. | `iface, ph03, shellKinds` |
| `docs/wiki/legacy/architecture/system-state-machine.md` | Describes `SYSTEM` as a reflective state machine over canonical subjects. | `legacy_reference` | `mixed` | `retain_as_legacy_reference` | Current migration docs still use it as supporting evidence for Hanus/shell structure, even though it is not v2 authority. | `ph03, ret, sai` |

Section recommendation: `partially harvest`

---

## 7. `docs/wiki/legacy/data-model/`

This subtree was meant to own semantic datum identity, write behavior, derived views, and file-backed data rules. It is valuable conceptually, but many file paths and storage owners are explicitly V1 and conflict with current v2 structural language.

Conflicts with current v2 authority:

- several pages list old resource/index artifacts as canonical
- route-level API details are used where v2 prefers port and adapter boundaries
- pages self-label as canonical despite the wiki’s non-authoritative status

Unique concepts worth preserving:

- semantic datum identity over storage position
- derived views as secondary projections
- mediation decode/encode defaults

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/wiki/legacy/data-model/README.md` | Topic index for legacy data-model rules. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Useful topic grouping, but the subtree cannot stay a canonical owner in the current v2 docs model. | `root, wikiR, auth` |
| `docs/wiki/legacy/data-model/canonical-data-artifacts.md` | Lists the file artifacts treated as canonical data. | `stale_conflict` | `accurate_for_v1_only` | `archive_only` | It hard-codes V1 artifact paths and inventories that should not be mistaken for current v2 truth. | `inv, naz, auth` |
| `docs/wiki/legacy/data-model/datum-identity-and-resolution.md` | Defines datum identity as canonical path rather than storage order. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The concept still aligns with v2 migration goals, but the page remains a legacy explanation rather than an authoritative v2 contract. | `inv, ret, sai` |
| `docs/wiki/legacy/data-model/datum-rule-policy.md` | Explains datum rule categories and write/publish policy. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Useful semantic policy material, but it is still embedded in V1 terminology and workflow assumptions. | `inv, naz` |
| `docs/wiki/legacy/data-model/derived-views.md` | Declares derived views secondary to canonical data. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Strong conceptual overlap with v2 derived-artifact rules, but it remains a legacy wiki statement. | `inv, naz` |
| `docs/wiki/legacy/data-model/external-resource-isolates.md` | Describes external resource isolate handling. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | No current v2 doc restates this concern cleanly, so it stays as legacy reference rather than active authority. | `auth, naz` |
| `docs/wiki/legacy/data-model/mediation-defaults.md` | Defines shared mediation encode/decode defaults. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The decode/encode registry idea is still useful, but the page is not a current v2 contract surface. | `iface, inv` |
| `docs/wiki/legacy/data-model/time-series-abstraction.md` | Describes anthology-only time-series abstraction. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Time-projection concepts still matter, but the page is a legacy explanatory surface. | `ret, sai` |
| `docs/wiki/legacy/data-model/write-pipeline.md` | Defines preview/apply write routes and semantic write flow. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The behavioral idea is useful, but the route-first contract conflicts with v2’s port/adaptor framing. | `inv, iface` |

Section recommendation: `partially harvest`

---

## 8. `docs/wiki/legacy/contracts-mss/`

This subtree was meant to explain MSS and contract context as a compact-array exchange surface. The subject still matters for retained concepts, but the wiki is not the current authority and the docs remain tightly tied to V1 page-model language.

Conflicts with current v2 authority:

- pages still treat `NETWORK > Contracts` as the canonical owner
- compact-array behavior is described through V1 UI/editor framing
- the subtree claims canonical status despite the wiki’s current non-authoritative role

Unique concepts worth preserving:

- semantic identity vs storage-local order
- compact-array MSS as scoped context
- contract update revisions

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/wiki/legacy/contracts-mss/README.md` | Topic index for contracts and MSS concepts. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Useful topic grouping, but no longer an authority surface under current docs governance. | `root, wikiR, auth` |
| `docs/wiki/legacy/contracts-mss/compiled-datum-index.md` | Explains identity-keyed compiled views over compact arrays. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Strong concept value remains, but the page is a legacy wiki explanation rather than a v2 contract. | `ret, sai, inv` |
| `docs/wiki/legacy/contracts-mss/contract-context-model.md` | Describes contract context fields and local behavior. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Still useful conceptually, but tied to the V1 `NETWORK` editor surface. | `auth, naz` |
| `docs/wiki/legacy/contracts-mss/contract-update-protocol.md` | Supporting note on revisioned contract update flow. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | No current v2 doc replaces it directly; it remains legacy reference rather than current truth. | `auth, naz` |
| `docs/wiki/legacy/contracts-mss/mss-compact-array.md` | Defines MSS as scoped compact-array context. | `legacy_reference` | `mixed` | `retain_as_legacy_reference` | It still carries retained concept value, but current v2 docs do not yet restate it as authoritative language. | `ret, sai` |

Section recommendation: `partially harvest`

---

## 9. `docs/wiki/legacy/samras/` and `docs/wiki/legacy/hops/`

These subtrees were not called out in the original batch order, but they are part of the actual legacy wiki tree and must be included for full coverage. They are the clearest examples of “retain as concept only”: the ideas still matter, but the pages are not current v2 authority.

Conflicts with current v2 authority:

- both are legacy wiki surfaces, not current ontology pages
- some wording is still V1-engine specific

Unique concepts worth preserving:

- SAMRAS as a shape-addressed structural model
- HOPS as retained chronology/time-projection structure

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/wiki/legacy/samras/README.md` | Topic index for SAMRAS structure and mutation rules. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The conceptual area clearly matters, but the wiki topic is not a current v2 authority surface. | `root, wikiR, ret` |
| `docs/wiki/legacy/samras/engine-ui-boundary.md` | Defines the engine/UI split for SAMRAS semantics. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The boundary is still useful conceptually, but the page remains a legacy explanation. | `inv, iface` |
| `docs/wiki/legacy/samras/structural-model.md` | Describes SAMRAS as a structural value and address space. | `legacy_reference` | `mixed` | `retain_as_legacy_reference` | It looks like retained concept material rather than outdated operational detail, but it is not yet a v2 ontology page. | `ret, sai` |
| `docs/wiki/legacy/samras/validity-and-mutation.md` | Explains SAMRAS validity and mutation invariants. | `legacy_reference` | `mixed` | `retain_as_legacy_reference` | The content still appears conceptually valuable, but it remains legacy reference until promoted. | `ret, sai` |
| `docs/wiki/legacy/hops/homogeneous_ordinal_partition_structure.md` | Defines HOPS as an ordinal partition structure for chronology and related spaces. | `legacy_reference` | `mixed` | `retain_as_legacy_reference` | Current migration docs explicitly retain HOPS as a concept source, even though the file is not current v2 authority. | `ret, sai` |

Section recommendation: `keep as reference`

---

## 10. `docs/wiki/legacy/sandbox-resources/`

This subtree was meant to separate sandbox lifecycle from resource inventory ownership. The lifecycle/orchestration split still aligns with v2, but several storage details remain V1-specific.

Conflicts with current v2 authority:

- storage examples still name old resource/index paths as canonical
- pages self-label as canonical despite the wiki’s current role

Unique concepts worth preserving:

- sandbox as lifecycle/orchestration boundary
- resource inventory separate from sandbox lifecycle
- inherited resource resolution as shared behavior

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/wiki/legacy/sandbox-resources/README.md` | Topic index for sandbox and resource rules. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The topic split is still useful, but the subtree is not a current authority surface. | `root, wikiR, naz` |
| `docs/wiki/legacy/sandbox-resources/inherited-resource-context.md` | Describes inherited resource context resolution. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The shared-resolution idea survives, but the page is framed through V1 route contracts. | `iface, naz` |
| `docs/wiki/legacy/sandbox-resources/resource-storage-and-ownership.md` | Separates resource inventory from sandbox ownership. | `stale_conflict` | `mixed` | `promote_unique_concepts` | The ownership split is useful, but the canonical paths listed are V1-specific and should not be reused as v2 truth. | `inv, naz` |
| `docs/wiki/legacy/sandbox-resources/sandbox-lifecycle.md` | Defines sandbox as the lifecycle layer for staging/compile/decode/adapt flows. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Strong overlap with v2 sandbox doctrine, but it remains a legacy wiki statement. | `iface, naz, inv` |

Section recommendation: `partially harvest`

---

## 11. `docs/wiki/legacy/network-hosted/`

This subtree was meant to explain the old `NETWORK` page, hosted sessions, progeny models, and request logs. Current v2 docs do not replace it directly, so it remains useful legacy reference, but it is heavily V1 page-model specific.

Conflicts with current v2 authority:

- rooted in the V1 `NETWORK` workbench model
- page/tab ownership is treated as canonical behavior
- storage and routing assumptions are V1 portal details

Unique concepts worth preserving:

- hosted-session derivation
- progeny/profile vocabulary
- request-log role as cross-portal evidence

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/wiki/legacy/network-hosted/README.md` | Topic index for legacy network/hosted behavior. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | No current v2 document replaces this area directly, so it remains a legacy reference surface. | `auth, naz` |
| `docs/wiki/legacy/network-hosted/hosted-sessions-and-alias-shell.md` | Explains hosted session derivation and alias-shell flow. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | Clear legacy behavior description, but tied to the V1 hosted model and page flow. | `auth, naz` |
| `docs/wiki/legacy/network-hosted/network-page-model.md` | Defines the V1 `/portal/network` page and tabs. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | Useful only as legacy page-model evidence; no v2 rollout doc makes it current truth. | `auth, naz` |
| `docs/wiki/legacy/network-hosted/progeny-and-profile-models.md` | Describes progeny terminology and profile-model expectations. | `legacy_reference` | `mixed` | `retain_as_legacy_reference` | Vocabulary may still matter later, but the model is still grounded in the V1 hosted/network surface. | `auth, naz` |
| `docs/wiki/legacy/network-hosted/request-log-and-audit.md` | Explains request-log purpose and storage. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | Remains useful as legacy operational evidence, not as a current v2 contract. | `auth, naz` |

Section recommendation: `keep as reference`

---

## 12. `docs/wiki/legacy/runtime-build/`

This subtree was meant to define build inputs, runtime composition, and instance configuration. Some repo-vs-live-state rules still align with current thinking, but the subtree includes one of the clearest stale conflicts in the legacy wiki.

Conflicts with current v2 authority:

- `shared-core-and-flavor-boundaries.md` places authority under `instances/_shared/portal/**`
- `build.json` and `private/config.json` are described through V1 instance-led runtime assumptions
- pages self-label as canonical inside a now non-authoritative zone

Unique concepts worth preserving:

- repo code vs live state separation
- build/materialization as bootstrap rather than live semantic owner
- config exposure vs datum authority distinction

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/wiki/legacy/runtime-build/README.md` | Topic index for runtime/build rules and host infra notes. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Repo/live-state and host-infra split still matter, but the page remains a legacy wiki overview. | `root, adr7, ph09` |
| `docs/wiki/legacy/runtime-build/build-and-materialization.md` | Defines `build.json` as a bootstrap materialization input. | `legacy_reference` | `accurate_for_v1_only` | `retain_as_legacy_reference` | Useful as legacy build/runtime evidence, but not a current v2 authority surface. | `auth, naz` |
| `docs/wiki/legacy/runtime-build/portal-config-model.md` | Describes `private/config.json` as runtime configuration authority. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The enabled-tools vs truth distinction is still useful, but the file remains V1 instance-config doctrine. | `ph07, ret, inv` |
| `docs/wiki/legacy/runtime-build/shared-core-and-flavor-boundaries.md` | Defines shared-core vs flavor boundaries through `instances/_shared/portal/**`. | `stale_conflict` | `superseded` | `archive_only` | It directly conflicts with current v2 structure and host-boundary decisions by centering authority in a V1 runtime tree. | `inv, adr7, ph09` |

Section recommendation: `partially harvest`

---

## 13. `docs/wiki/legacy/tools/`

This subtree was meant to explain tools as shell-attached providers, plus a few product-specific tool surfaces. Much of its doctrine still matches v2 direction, but the subtree is legacy reference because it expresses the doctrine through V1 runtime and product surfaces.

Conflicts with current v2 authority:

- product-specific AGRO, PayPal, and member-service details are mixed with general tool doctrine
- routes and query-launch contracts are described directly in the wiki
- the subtree still labels itself canonical

Unique concepts worth preserving:

- tools are providers, not shells
- tool mediation is shell-hosted
- internal file sources should stay read-only and mediated

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/wiki/legacy/tools/README.md` | Topic index for tool doctrine and tool-specific pages. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The shell-hosted provider model aligns with v2, but the wiki is not the active authority surface. | `ph07, adr4, iface` |
| `docs/wiki/legacy/tools/agro-erp-datum-decision-ledger.md` | Staging ledger for AGRO datum-family decisions. | `historical_evidence` | `accurate_for_v1_only` | `archive_only` | A product staging ledger, not a stable contract or current v2 authority source. | `auth, naz` |
| `docs/wiki/legacy/tools/agro-erp-mediation.md` | Describes AGRO-ERP mediation through the unified shell. | `legacy_reference` | `mixed` | `retain_as_legacy_reference` | The shell-attached mediation idea remains useful, but the page is product-specific V1 behavior. | `ph07, adr4, iface` |
| `docs/wiki/legacy/tools/internal-file-sources.md` | Defines mediated read-only access to internal operational files. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Strong reusable rule, but it still lives as a legacy wiki page rather than a current v2 contract. | `ph07, iface, naz` |
| `docs/wiki/legacy/tools/member-service-integrations.md` | Describes member-scoped provider integrations such as PayPal. | `legacy_reference` | `mixed` | `retain_as_legacy_reference` | Still useful legacy integration context, but not current v2 doctrine. | `auth, naz` |
| `docs/wiki/legacy/tools/provider-model.md` | States that tools are providers, not shells. | `legacy_reference` | `mixed` | `promote_unique_concepts` | One of the strongest carry-forward doctrine pages, but it remains a legacy source rather than v2 authority. | `ph07, adr4, iface` |
| `docs/wiki/legacy/tools/time-address-schema.md` | Describes AGRO time-address schema and encoding. | `legacy_reference` | `mixed` | `retain_as_legacy_reference` | Closely related to retained HOPS/time-projection ideas, but not yet promoted into current v2 docs. | `ret, sai` |
| `docs/wiki/legacy/tools/tool-layer-mediation.md` | Defines launch/context contract for shell-hosted tool mediation. | `legacy_reference` | `mixed` | `promote_unique_concepts` | Strong doctrine overlap with v2 tool attachment, but still encoded as V1 route/context language. | `ph07, adr4, iface` |

Section recommendation: `partially harvest`

---

## 14. `docs/wiki/legacy/governance/`

This subtree was meant to define how the wiki and surrounding docs were maintained. It now contains the clearest governance drift in the legacy tree.

Conflicts with current v2 authority:

- it says `docs/wiki` is the primary maintained conceptual knowledge base
- it still references `docs/modularity/` and `docs/archive/` as active governance roots
- it predates the current authority stack and non-authoritative-zone doctrine

Unique concepts worth preserving:

- repo docs vs live runtime-state boundary

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/wiki/legacy/governance/README.md` | Topic index for old documentation governance and repo boundaries. | `stale_conflict` | `superseded` | `archive_only` | The subtree framing itself reflects a governance model replaced by the current authority stack. | `root, wikiR, auth, naz` |
| `docs/wiki/legacy/governance/documentation-governance.md` | Defines the old documentation classification and precedence model. | `stale_conflict` | `superseded` | `archive_only` | It directly conflicts with the current docs governance by making the wiki the primary maintained knowledge base. | `root, wikiR, auth, naz` |
| `docs/wiki/legacy/governance/repository-boundaries.md` | Explains repo code vs live runtime-state boundaries. | `legacy_reference` | `mixed` | `promote_unique_concepts` | The core boundary remains sound, but the page lives inside a stale governance subtree and should be harvested into current docs if still needed. | `root, inv, adr7` |

Section recommendation: `archive`

---

## 15. `docs/wiki/legacy/archive/`

This subtree already presents itself as lineage-only material. Its purpose still makes sense, but it should stay clearly historical.

Conflicts with current v2 authority:

- none beyond being in a non-authoritative zone by design

Unique concepts worth preserving:

- only lightweight lineage notes

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/wiki/legacy/archive/README.md` | Explains archive pages as lineage-only notes. | `historical_evidence` | `mixed` | `archive_only` | Its purpose is still correct, but it is intentionally non-authoritative and historical. | `naz, root` |
| `docs/wiki/legacy/archive/historical-lineage.md` | Lists superseded models retained for lineage context. | `historical_evidence` | `mixed` | `archive_only` | This is historical context by design and should remain clearly archived. | `naz, root` |

Section recommendation: `archive`

---

## 16. `docs/wiki/legacy/todo/`

This subtree holds deferred-development notes rather than settled truth. One file still contains useful AWS inbound-removal context; the other is explicitly superseded.

Conflicts with current v2 authority:

- neither file is a stable ownership surface
- one file is explicitly superseded

Unique concepts worth preserving:

- inbound-removal dependencies and sequencing context

| path | purpose | authority_class | truth_status | recommended_action | reason | comparison_sources |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/wiki/legacy/todo/legacy_inbound_removal_context.md` | Records rationale, risks, and sequencing for removing legacy inbound forwarding. | `legacy_reference` | `mixed` | `retain_as_legacy_reference` | Still useful follow-on context for AWS onboarding/inbound work, but it is a deferred note rather than current authority. | `awsFirst, band4, naz` |
| `docs/wiki/legacy/todo/newsletter_separate_tool_context.md` | Deferred note for separate newsletter tool context. | `historical_evidence` | `superseded` | `archive_only` | The file says it is superseded and conflicts with the corrected AWS/newsletter posture. | `awsFirst, naz` |

Section recommendation: `archive`

---

## First-Pass Outcome

The first-pass audit is complete for all 88 files in:

- `docs/plans/legacy/`
- `docs/contracts/legacy/`
- `docs/wiki/legacy/`

Resulting organization buckets:

- **Current V2 authority:** none in reviewed scope
- **Retained legacy reference:** keep mailbox/onboarding, Hanus/tool doctrine, MSS/SAMRAS/HOPS, selected network/runtime/tool concept pages as legacy evidence
- **Historical evidence:** keep transcripts, reports, lineage notes, and staging ledgers clearly archived
- **Cleanup candidates:** stale governance pages, duplicate superseded newsletter notes, and old path-inventory docs after their unique concepts are harvested
