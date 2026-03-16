# AGRO-ERP MVP Contract (TXA-First)

## Happy Path

1. Operator opens AGRO-ERP.
2. Operator selects a **txa** inherited resource.
3. `Resource` tab shows inherited resource summary (id, kind, origin, compile status, digest, bindings).
4. `Product Types` tab runs preview/apply for one product-profile write from inherited txa context.
5. `Invoice Log` tab runs preview/apply for one invoice-log write from inherited txa context.
6. Both writes use shared preview/apply flow.
7. Both tabs show post-write readback.
8. Local writes stay minimal and no txa subtree is materialized into anthology.

## In Scope

- TXA-first inherited write flow.
- Thin three-tab AGRO UX (`Resource`, `Product Types`, `Invoice Log`).
- Shared-core orchestration only (sandbox/data_engine/mss services).
- Local-origin and foreign-origin txa parity through one adapter path.
- Live-like FND validation and end-to-end tests.

## Out of Scope (MVP)

- msn inherited workflow unless required by a concrete MVP write path.
- Anthology schema redesign.
- Sandbox architecture redesign.
- UI-heavy sandbox expansion.
- Route-local MSS/SAMRAS semantics in AGRO endpoints or templates.

## MVP Invariants

- Sandbox resource JSON remains source-of-truth for full txa/msn resource content.
- Anthology must not re-introduce full txa subtree (`4-1-*`) after preview/apply flows.
- Shared-core owns MSS/SAMRAS semantics, inherited-context adaptation, and write staging.
