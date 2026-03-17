# AGRO-ERP and Portal Data Foundation — Intention

> **Status: Background/design-intent document (non-canonical).**
> Canonical current behavior is in `AGRO_ERP_TOOL.md`, `CANONICAL_DATA_ENGINE.md`, and `SANDBOX_ENGINE.md`.

This document captures **goals, design decisions, and boundaries** for the AGRO-ERP tool and the shared foundation it depends on. It is separate from implementation and progress tracking.

---

## Goals

- **Polish and tune** the current implementation so it does not restrict later development; apply only changes that are low-regret and foundational.
- **Solidify foundation first**: datum identity, public resolution path, and contract compact-array model — then expand AGRO-ERP functionality.
- **Contract compact array**: support updates and recompilation while handling specific datums via **datum paths** as unique, unambiguous identifiers. One portal may update or add datums; the compact array is recompiled and updates sent via request log for the receiving side.
- **Contracts**: allow one-sided storage (only the referencing portal holds the contract). When both portals use the contract, either may update the compact array; recompilation and update flow must be defined.
- **AGRO-ERP direction**: evolve into a **broader agricultural data tool**; docs/API contract will be rewritten over time. Current scope: property geometry; planned: inherited taxonomy, product types, field records, crop references.
- **Public resolution**: anonymous/public resolver path driven from the contact card’s **accessible / exported datum metadata**; public datums resolvable without requiring a contract.
- **Request log**: used **only** when TFF actually accesses or negotiates external FND resources (remote access, compact-array refresh, update notices, contract negotiation). **Not** used for local AGRO-ERP CRUD on product types or other local tool writes. Local tool CRUD must use the **local audit log** (`portal.services.local_audit_log.append_audit_event`); see CONTRACT_UPDATE_PROTOCOL and HOSTED_SESSIONS for the same rule.

---

## Design Decisions (to settle now)

1. **Datum path = semantic identity.** Local anthology row ids (layer / value_group / iteration) are **storage addresses**, not semantic identity. The same datum may have different addresses in different anthologies or after compaction.
2. **Contract may exist without encryption.** A contract is a relationship state file; asymmetric signatures and symmetric keys are optional. Encryption must not be required for “freely accessible” or open-access data.
3. **Public/exported datums** must resolve without requiring a contract. Resolution order must put public contact-card exported metadata before contract-based resolution.
4. **Compact arrays** are **revisioned compiled snapshots**, not ad hoc lists. Entries are keyed by canonical datum path so recompilation does not break identity.
5. **Request log** is for **external resource access and negotiation only**. Local tool CRUD and data-engine writes use a **separate log surface** (e.g. runtime action log, data-engine audit log, or tool-local event log).
6. **One-sided and two-sided contracts** are explicit. Contract schema should support modes such as unilateral (only referencing portal stores it), mirrored (both store compatible copies), and negotiated (both store and coordinate updates).

---

## Resolution Order (canonical)

1. Local anthology  
2. Local projection cache  
3. Local contract compact-array snapshot  
4. **Public contact-card exported datum metadata**  
5. Remote fetch / resolution  
6. Negotiated / private contract path  

Public resolution is a first-class path and does not require contract resolution first.

---

## Contract Compact Array (intended shape)

The contract’s compact array is treated as a **compiled datum index** with structure along these lines:

- `contract_id`, `relationship_mode`, `authority_mode`, `access_mode`
- `source_msn_id`, `target_msn_id`
- `revision`, `compiled_at_unix_ms`, `source_card_revision`
- `entries`: keyed by **canonical datum path** (not by local order)

Each entry: `datum_path`, `scope`, `access`, `source_kind`, `source_ref`, `display_title`, `magnitude_hint`, `mediation_hint`, `updated_unix_ms`, `revision`.  

Recompilation can then change order or iteration without breaking identity.

---

## Contract Modes (intended)

- **unilateral_local**: only the referencing portal stores the contract.  
- **mirrored_shared**: both portals store compatible copies.  
- **negotiated_shared**: both store and expect update coordination.  

Additional dimensions:

- **access_mode**: `public | contract | private`  
- **sync_mode**: `none | pull_refresh | push_notified | negotiated`  

These should be part of the contract schema so behavior is explicit, not inferred.

---

## Compact-Array Update Protocol (intended)

When one portal updates or adds datums to the compact array:

- **Revisioned patch model**: operations such as `replace_snapshot`, `add_entry`, `update_entry`, `remove_entry`, `recompile`, `acknowledge_revision`.
- Update messages carry: `contract_id`, `from_revision`, `to_revision`, `changed_paths`, `change_type`, `source_msn_id`, `target_msn_id`, `ts_unix_ms`.
- For **external** updates, send evidence through **request_log**; the log carries update evidence, not the authoritative state. The actual contract state remains in the contract file.

---

## What Not to Freeze Yet

- Fixed product-type **layer / value_group** numbers in a permanent base schema.  
- Full AGRO-ERP save schema for every future agricultural record type.  
- Mandatory two-sided contract assumption.  
- Contract-required access for public FND taxonomy data.  
- Use of request_log as a generic local event bus.  

The lowest-risk approach is to build the **shared identity + resolver + contract snapshot foundation** first; AGRO-ERP can then expand without forcing rework across the data engine, contracts, and network model.

---

## AGRO-ERP Interim Framing

- **AGRO-ERP** = agricultural data workbench.  
- **Current capability**: property geometry (coordinate resolution).  
- **Planned capabilities**: inherited taxonomy, product types, field records, crop references.  

Define tool-spec **inputs/outputs** and **capability buckets**, but avoid hardcoding current coordinate-only semantics as the permanent identity of the tool. Do not lock the full API contract until the three foundations (datum identity, public resolver, compact-array contract update model) are stable.

Current implementation uses planner-first orchestration over canonical `/portal/api/data/*` write preview/apply routes (plus external-resource planner endpoints when needed); AGRO-ERP remains an operational layer, not the semantic authority.

---

## Implementation Order (preferred)

1. Datum identity module  
2. Contract compact-array schema + compiler  
3. Public / contact-card datum resolver  
4. Contract update protocol  
5. Tool-spec schema (inherited inputs, outputs, optional storage anchors; keep bindings loose)  
6. Local audit log distinct from request_log  
7. AGRO-ERP doc reframing (purpose, capability buckets)  
8. AGRO-ERP inherited taxonomy / product functionality (building on the above)  

---

## Boundary: Keep Compact-Array Semantics Out of AGRO-ERP

AGRO-ERP should consume:

- Normalized inherited datum handles  
- Normalized taxonomy trees  
- Stable canonical refs  
- Declared output archetypes  

It should **not** implement contract snapshot recompilation or compact-array compilation rules. That logic belongs in shared services; the tool depends on them via clear interfaces.

---

## MVP execution lock (TXA-first)

Near-term MVP is intentionally narrow:

- inherited **txa** resource is required for product-profile and invoice-log flows
- inherited msn workflow is deferred unless required by a concrete MVP write path
- AGRO backend orchestrates shared-core services, not route-local MSS/SAMRAS semantics
- AGRO UI remains thin and tab-based (`Resource`, `Product Types`, `Invoice Log`)

Core invariants for MVP:

- sandbox resource JSON is source-of-truth for full txa/msn resource content
- anthology does not re-materialize full `4-1-*` txa subtree after preview/apply
- writes remain minimal-local and config-ref surfaced through shared write pipeline
