# AGRO-ERP

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `carry_forward`  
V2 tool id target: `agro_erp`  
Config gate target: `tool_exposure.agro_erp`  
Audience: `internal-admin` first, later audience review

## Current code, docs, and live presence

- Current code: no V2 `agro_erp` registry entry or runtime entrypoint exists.
- Legacy evidence: V1 AGRO/HOPS planning, datum/time schema docs, and live FND
  `agro-erp` utility and sandbox roots still exist.
- Live presence: FND still has `private/utilities/tools/agro-erp/` and
  `data/sandbox/agro-erp/sources/`; TFF does not.

## Reusable evidence vs legacy baggage

- Reusable evidence: HOPS/SAMRAS-aligned datum families, property/timing
  inspection, and tool-local sandbox/source needs.
- Legacy baggage: broad mediation UI, legacy chronology contracts, and tool-owned
  shell behavior.

## Required V2 owner layers and dependencies

- Shell registry: new future `agro_erp` descriptor only after Maps stabilizes.
- Runtime entrypoint: one new admin read-only entrypoint first.
- Semantic owner: AGRO-oriented module above datum recognition and authoritative
  document reads.
- Port and adapter: authoritative datum reads plus any future non-datum AGRO
  utility seam.
- State dependency: `data/sandbox/agro-erp/sources/*.json` and explicit tool
  utility state only.

## Admin activity-bar behavior

- Hidden and blocked unless `tool_exposure.agro_erp.enabled=true`.
- No activity-bar presence before Maps and the datum-inspection path are proven.
- Admin-first only in the first pass.

## Carry-forward and do-not-carry-forward

- Carry forward AGRO-ERP as a later datum-backed admin tool after Maps.
- Do not reuse V1 route trees or mixed tool/workbench composition.
