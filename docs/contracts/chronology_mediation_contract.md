# Chronology Mediation Contract

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

Chronology is a mediation concern in forward V2, not an active tool family in
the current queue.

## Core rule

- `Calendar` is not a current V2 `tool_id`.
- `tool_exposure.calendar` is not part of the forward contract.
- chronology renders through shell/interface surfaces after slice approval,
  rather than through a standalone tool packet entry.

## Authority

- declared event documents remain source truth
- HOPS-governed partitioning remains the chronological ordering rule
- rendered timelines, cards, grouped lists, and future calendar views are
  derived mediation only

## Placement

- current placement is under shell/interface-panel mediation
- future work may add chronology-specific read-only surfaces without reviving a
  `calendar` tool registry row

## Immediate implementation rule

- remove chronology from the active tool queue
- document chronology under mediation and interface-surface rules
- defer any writable chronology behavior until a later explicit slice approval
