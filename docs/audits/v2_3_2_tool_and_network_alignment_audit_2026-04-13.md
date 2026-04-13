# V2.3.2 Tool And Network Alignment Audit

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

Date: 2026-04-13

This audit classifies the repo changes required by the V2.3.2 tool and network
rework.

## Executive result

- Keep: the shell-owned root model and the dual-gate `tool_exposure` posture.
- Update: tool taxonomy, spatial naming, network guidance, and rollout docs.
- Retire: `default tool` vocabulary, `Calendar` as an active tool-packet item,
  and `tenant_progeny_profiles` as the placeholder hosted/progeny entrypoint.

## Superseded audit guidance

The 2026-04-12 audit correctly identified drift, but any statement that V2 was
still missing active `tool_exposure` support is now superseded by current code
and contracts. The gap is no longer implementation absence; it is taxonomy and
documentation alignment.

## Keep

- `System`, `Network`, and `Utilities` as shell roots
- shell-owned tool legality and routing
- `tool_exposure` as the instance visibility gate
- archival `docs/wiki/legacy/**` and legacy datum evidence as historical
  reference only

## Update

- `maps` canonical naming to `CTS-GIS`
- tool descriptors and runtime catalogs to carry `tool_kind` and optional
  shared capability declarations
- tool packet indexes and rollout docs so they describe tools by shell
  attachment plus `tool_kind`
- `/portal/network` copy so it reflects contract-first hosted/P2P work

## Retire Or Reclassify

- `default tool` as forward V2 vocabulary
- `tool_exposure.calendar`
- `docs/plans/v2.3-tool_surface_packet/tenant_progeny_profiles.md` as an active
  plan
- `docs/plans/v2.3-tool_surface_packet/maps.md` and
  `docs/contracts/admin_maps_read_only_surface.md` as authoritative names

## Immediate repo work

### Taxonomy

- keep root services outside the tool registry
- require `tool_kind` in shell-owned tool descriptors
- reserve `host_alias_tool` without implementing it yet

### CTS-GIS

- use `cts_gis` in code, tests, docs, routes, and config gates
- preserve legacy sandbox datum evidence under `sandbox/maps/**` only as
  compatibility data
- treat `CTS-GIS` as a `general_tool`, not a default app

### Chronology

- move chronology planning under mediation contracts
- do not add a `calendar` runtime stub, registry row, or exposure key

### Network

- approve hosted/network contracts before any host-alias runtime work
- keep `/portal/network` lightweight until those contracts are implemented
