# MOS Directive-Context Design Track

Date: 2026-04-21

Doc type: `plan`  
Normativity: `supporting`  
Lifecycle: `active`  
Last reviewed: `2026-04-21`

## Purpose

Advance Track C from `docs/plans/master_plan_mos.md` by defining the scope, schema, and update-policy posture for future NIMM/AITAS directive-context integration without turning it into a blocker for the SQL-backed core.

## Scope

In scope:

- future insertion points for directive-context behavior
- directive-context schema candidates keyed to Track B semantic identity
- update and conflict policies for directive-context snapshots
- boundaries between shared shell behavior and tool-local behavior

Out of scope:

- promoting directive-context behavior into shared-engine canon during the v1 SQL cutover
- rewriting the shared shell around NIMM/AITAS
- redefining current tool-local CTS-GIS mediation as shared-engine truth

## Directive-Context Posture

1. Directive context is a **semantic overlay**, not a replacement for authoritative datum rows.
2. Directive context must key to Track B outputs:
   - `version_hash` for storage-bound snapshots
   - `hyphae_hash` for stable semantic subjects
3. Directive context may shape navigation, attention, mediation, and manipulation posture, but it does not rewrite authoritative datum identity.
4. Until a later widening decision, directive context remains tool-local by default and shared-shell-visible only through explicitly approved surfaces.

## Insertion Points

1. Shared shell posture
   - future insertion only after stable semantic identity and remap behavior are available
   - shared shell consumes normalized directive summaries, not raw tool-local state
2. Domain services
   - may interpret directive overlays keyed by `hyphae_hash` and `version_hash`
   - may expose summarized subject, intention, and workspace posture
3. Tool-local mediation
   - remains the active home for NIMM/AITAS-like experimentation
   - CTS-GIS retains local ownership until a later canon decision

## Proposed Schema

If Track C widens into SQL authority later, the first schema should be additive and reference the existing SQL-backed core:

- `directive_context_snapshots`
  - `context_id`
  - `portal_instance_id`
  - `tool_id`
  - `hyphae_hash`
  - `version_hash`
  - `payload_json`
  - `updated_at_unix_ms`
- `directive_context_events`
  - append-only change log for review, replay, and rollback
  - keyed for lookup by `portal_instance_id`, `tool_id`, `hyphae_hash`, `version_hash`
  - never treated as the authoritative datum store

## Canonical Field Expectations

- `hyphae_hash`
  - stable semantic subject handle at the SQL lookup boundary
- `version_hash`
  - binds a directive snapshot to one storage-version posture when needed
- `payload_json`
  - normalized port payload containing `nimm_state`, `aitas_state`, `scope`, and `provenance`
- `provenance_json`
  - tool-local source, confidence, and ownership notes

## Update Policy

1. Directive context is **replace-by-snapshot** at the shared boundary.
2. Tool-local systems may keep richer transient state, but only normalized snapshots cross into shared storage.
3. Shared directive writes must be rejected if they do not bind to a valid `hyphae_hash` or an explicitly declared non-datum subject.
4. Directive snapshots must not mutate authoritative datum rows directly.
5. Shared-shell consumers should tolerate missing directive context and fall back to file/workbench-oriented behavior.

## Interface with the SQL-Backed Core

Once Track B is closed, directive-context integration should read from, but not overwrite:

- `datum_document_semantics.version_hash`
- `datum_row_semantics.hyphae_hash`
- portal-authority scope data for grants/tool exposure

The intended interface order is:

1. authoritative SQL datum-store resolves document and row semantics
2. directive-context layer binds overlays to those semantics
3. runtime composes shell or tool posture from the overlay only where approved

## Approved Implementation Pass

The current repo now implements the first non-blocking Track C seam:

- `directive_context_snapshots` and `directive_context_events` exist as additive SQL tables
- a dedicated directive-context port and SQL adapter exist
- the approved shared runtime seam is the system workspace selection path
- the runtime reads overlays only after resolving `version_hash` and `hyphae_hash`
- the runtime composes directive context additively and never mutates datum rows

## V1 Non-Goals

- no shared-shell archetype selector
- no SQL cutover dependency on directive-context closure
- no assumption that current tool-local mediation vocabulary is already universal engine canon
- no directive writes that bypass Track B semantic identities

## Exit Criteria

- insertion points are explicit
- schema candidates are explicit
- update policies are explicit
- interface dependencies on Track B are explicit
- Track C can progress without reopening Track A or Track B
