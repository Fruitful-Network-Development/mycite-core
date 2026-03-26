# AGRO-ERP Datum Decision Ledger

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Tools](README.md)

## Status

Canonical staging ledger

## Purpose

Capture AGRO datum-family decisions that must be frozen before deeper implementation, while explicitly separating what is already active now (empty dual-pane mediation) from deferred model commitments.

## Implemented Now (Locked)

- AGRO opens through `SYSTEM` mediation only (`/portal/system?mediate_tool=agro_erp`).
- Default AGRO mediation mode is the dual-pane empty scaffold:
  - `spatial` (left operational pane, right contextual companion)
  - `chronological` (left operational pane, right contextual companion)
- Legacy AGRO modes remain available as secondary compatibility modes.
- Empty scaffold load is non-failing even when browse/session activation is unresolved.
- Core session + shell authority remains shared-core; AGRO does not own shell state.

## Decision Ledger

Each topic includes current freeze state and implementation boundary.

1. **Whole-sandbox attention and mediation scope**
   - State: **Frozen**
   - Decision: AGRO mediation runs at sandbox depth (`focus_depth=0`) with no required datum selection.
   - Boundary: no tool-home shell, no separate AGRO shell.

2. **AGRO local anchor identity**
   - State: **Frozen**
   - Decision: per-tool anchor follows `tool.<msn_id>.agro-erp.json` under `private/utilities/tools/agro-erp/`.
   - Boundary: anchor is configuration/projection root, not a second anthology.

3. **Coordinate representation and coordinate datum mediation**
   - State: **Open**
   - Pending decision: canonical coordinate encoding for authored local commits vs inherited decode views.
   - Boundary now: scaffold/UI only; no new coordinate write schema introduced.

4. **Parcel identity**
   - State: **Open**
   - Pending decision: stable parcel identifier namespace (`parcel_id`) across inherited/local scopes.
   - Boundary now: read-only parcel displays from existing workspace sources.

5. **Parcel geometry and bounding-box reference structure**
   - State: **Open**
   - Pending decision: canonical tuple/reference structure for polygon + bbox refs.
   - Boundary now: no schema migration of geometry storage.

6. **Plot and grid overlay resource structure**
   - State: **Open**
   - Pending decision: persisted draft schema and identity lifecycle for grid overlays.
   - Boundary now: retain MVP draft behavior; do not hard-freeze final overlay schema.

7. **Product profile datum structure**
   - State: **Open**
   - Pending decision: canonical minimal field family for product profile datums.
   - Boundary now: existing preview/apply routes stay compatibility-only.

8. **Supply log / invoice log datum structure**
   - State: **Open**
   - Pending decision: chronology/event binding fields and ledger rollup invariants.
   - Boundary now: existing supply-log preview/apply remains unchanged.

9. **TXA role binding semantics**
   - State: **Open**
   - Pending decision: role key set and requiredness (`taxonomy_ref`, selector refs, fallback chain).
   - Boundary now: no new role-key contract enforced.

10. **MSN role binding semantics**
    - State: **Open**
    - Pending decision: inheritance identity mapping and alias resolution precedence.
    - Boundary now: use existing resolver behavior.

11. **ERP role binding semantics**
    - State: **Open**
    - Pending decision: AGRO-local operational roles and promotion/commit gates.
    - Boundary now: no new write authority tier.

12. **Local AGRO datum-family ranges and identifier layout**
    - State: **Open**
    - Pending decision: reserved family/layer/id ranges for AGRO-local datum writes.
    - Boundary now: do not allocate new permanent ranges.

13. **Chronology, schedule, and retrospective record structure**
    - State: **Open**
    - Pending decision: canonical event/schedule datum schema and rollup references.
    - Boundary now: chronological pane is visual scaffold only.

14. **Left-plane operational subject vs right-plane contextual companion**
    - State: **Frozen**
    - Decision: dual-plane semantics are canonical for AGRO default mediation.
    - Boundary: implementation detail inside panes remains iterative; plane responsibility is fixed.

15. **Inherited-resource boundary vs local materialization boundary**
    - State: **Frozen**
    - Decision: inherited resources remain browse/context truth; local materialization remains explicit and minimal.
    - Boundary: no bulk subtree materialization into anthology.

16. **Minimal local commit and readback surface for AGRO workflows**
    - State: **Frozen**
    - Decision: keep commit surface narrow and auditable; readback remains mandatory for applied flows.
    - Boundary: defer broader write orchestration redesign.

## Next Freeze Gate

Before implementing non-empty spatial/chronological data panes, freeze items 3-13 as a single schema decision set (or explicitly split into phased freezes with compatibility contracts).
