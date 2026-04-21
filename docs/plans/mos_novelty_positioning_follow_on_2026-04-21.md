# MOS Novelty Positioning Follow-On

Date: 2026-04-21

Doc type: `positioning-note`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-21`

## Purpose

Promote the strongest durable ideas from the MOS novelty note into a clean internal positioning/spec note that stays separate from operational cut-over docs.

## Boundary

- This is an internal positioning/spec note, not a closure artifact.
- This is not legal advice, a patent opinion, or a substitute for formal prior-art review.
- Operational cut-over authority remains in `docs/plans/master_plan_mos.md` and the related closure audits.

## Positioning Core

The durable internal positioning for MOS is:

**MOS is a datum-native semantic grammar in which authoritative documents remain file-shaped, datum rows remain structurally ordered, document identity is storage-derived through `version_hash`, row identity is semantic-derived through `hyphae_hash`, and interoperable inspection can happen without collapsing participants into one shared application schema.**

## Durable Claims

1. MOS is datum-native rather than node-first, triple-first, or record-first.
   - The repo's active contracts and workbench surfaces treat authoritative documents and datum rows as the first inspection units.

2. MOS uses dual canonicality.
   - `version_hash` canonizes storage identity for authoritative documents.
   - `hyphae_hash` canonizes semantic identity for datum rows.

3. MOS keeps structural coordinates explicit.
   - `layer`, `value_group`, and `iteration` remain visible storage coordinates rather than being hidden behind opaque graph IDs.

4. MOS preserves additive overlays as separate from datum authority.
   - Directive context may shape posture and inspection, but it does not rewrite authoritative datum rows.

5. MOS should be described as an interoperability and abstraction system, not merely as a database category.
   - The storage backend can change; the more durable claim is the grammar, identity, and abstraction model.

## Prior-Art Matrix

| Prior art family | What it primarily canonicalizes | Where MOS differs | What MOS should not overclaim |
|---|---|---|---|
| Property graphs | nodes, edges, labels, properties, and store-specific graph identity | MOS keeps file-shaped authority, visible structural coordinates, and a separate row-semantic identity layer | do not claim MOS invented relationship-centric data modeling |
| RDF / JSON-LD | subject-predicate-object statements plus linked-data contexts and graph interoperability | MOS keeps ordered datum rows, anchor-context identity, and a file/workbench-oriented authority surface | do not claim MOS invented linked-data interoperability |
| Avro | schema form, schema compatibility, and schema fingerprints | MOS canonicalizes authoritative document content and row semantic closure, not only schema | do not claim MOS invented canonicalization or fingerprinting |
| IPLD | content-addressed blocks, links, and selector-based traversal | MOS separates storage identity from semantic row identity inside authoritative datum documents | do not claim MOS invented content addressing or traversal over linked content |
| Append-only event systems | ordered event history and replayable change logs | MOS treats event logs as supporting evidence or overlays, not as the authoritative datum-row substrate | do not claim MOS invented append-only history or immutable logs |

## Internal Usage Guidance

Use this note when:

- describing MOS to internal collaborators
- reviewing whether web copy or internal docs overclaim novelty
- distinguishing MOS from storage-engine categories

Do not use this note as:

- the authority for operational cut-over scope
- proof that every aspirational MOS concept is already implemented
- justification for widening shared-engine NIMM/AITAS canon in this pass

## Evidence Anchors

- `docs/plans/master_plan_mos.md`
- `docs/plans/mos_sg1_version_identity_policy_2026-04-21.md`
- `docs/plans/mos_sg2_hyphae_derivation_policy_2026-04-21.md`
- `docs/plans/mos_sg3_edit_remap_policy_2026-04-21.md`
- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/surface_catalog.md`

## Result

The strongest durable novelty claims are now separated from cut-over operations. The repo can describe MOS as a datum-native semantic grammar with dual canonicality and explicit structural coordinates while avoiding overclaiming novelty already occupied by graphs, linked data, schema fingerprints, content addressing, or append-only event systems.
