# Maps

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `current_v2`  
V2 tool id target: `maps`  
Config gate target: `tool_exposure.maps`  
Audience: `internal-admin` first, later audience review

## Current code, docs, and live presence

- Current code: V2 now has a shell-owned `maps` descriptor, runtime entrypoint
  `admin.maps.read_only`, a direct host route
  `POST /portal/api/v2/admin/maps/read-only`, and shell render kinds
  `maps_workbench` plus `maps_summary`.
- Legacy evidence: V1 planning/docs and live FND sandbox source trees still
  exist for maps data and remain the historical evidence used to bound the V2
  carry-forward logic.
- Live presence: FND has `tool_exposure.maps.enabled=true` and the current V2
  admin shell exposes Maps there. TFF remains hidden and blocked. FND still has
  `private/utilities/tools/maps/` and `data/sandbox/maps/sources/`; TFF does
  not have a comparable sandbox.

## Reusable evidence vs legacy baggage

- Reusable evidence: authoritative sandbox datum documents, non-sequential
  addresses, source-backed inspection needs, and the pure bounded HOPS
  coordinate decoding behavior needed for `HOPS-babelette-coordinate`.
- Legacy baggage: V1 mediation chrome, generalized mediation registries,
  config-driven mount rules, and tool-owned UI behavior.

## Required V2 owner layers and dependencies

- Shell registry: `maps` is now a shell-owned descriptor in the V2 admin tool
  registry.
- Runtime entrypoint: `admin.maps.read_only` is now the read-only admin
  entrypoint.
- Semantic owner: `packages/modules/cross_domain/maps/` now sits above the
  datum-recognition seam.
- Port and adapter: authoritative datum document reads are still reused from
  `packages/ports/datum_store/` through the current filesystem adapter.
- State dependency: authoritative reads are limited to `data/system/anthology.json`,
  `data/sandbox/maps/tool.maps.json`, and `data/sandbox/maps/sources/*.json`.

## Admin activity-bar behavior

- Hidden and blocked unless `tool_exposure.maps.enabled=true`.
- Current live rollout is admin-first and FND-only.
- Direct launch is also blocked with `tool_not_exposed` when disabled.

## Carry-forward and do-not-carry-forward

- Carry forward only the read-only datum-backed inspection and bounded overlay
  behavior now implemented in V2.
- Do not recreate V1 tool mediation, config-owned launch rules, or config-owned
  routing/order semantics.
