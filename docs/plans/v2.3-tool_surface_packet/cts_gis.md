# CTS-GIS

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Canonical name: `CTS-GIS`\
Packet role: `implemented family root`\
Queue posture: `implemented general-tool family; FND-first admin deployment complete`\
Current live tool id: `cts_gis`

## Current family truth

- current code ships the admin read-only CTS-GIS slice under `Utilities`
- canonical live ids are `cts_gis`,
  `admin_band5.cts_gis_read_only_surface`,
  `admin.cts_gis.read_only`, and `/portal/utilities/cts-gis`
- compatibility datum evidence may still live under `sandbox/maps/**`
- the dominant interface panel is the live Hanus lens surface for GeoJSON,
  attention, and intention mediation
- the workbench remains mounted as background evidence and raw-inspection
  context

## Tool classification

- CTS-GIS is a `general_tool`
- it is not a shell root
- it is not a `default_tool`
- it is not a hosted/network family

## Current implemented slice

The implemented slice is the FND-first admin read-only CTS-GIS Hanus lens
surface.

It keeps:

- authoritative datum-first reads
- read-only projection and overlay rendering
- dominant interface-panel GeoJSON mediation with server-issued
  attention/intention state
- diagnostic-first handling of unresolved spatial values
- shell-owned launch legality with `tool_exposure.cts_gis`

## Current stability rules

1. keep CTS-GIS naming stable across code, docs, tests, and deploy config
2. preserve the current FND-first rollout gate while deploying shared portal
   code to both live portals
3. preserve legacy sandbox datum compatibility without reviving `maps` as the
   live tool id
4. keep future spatial expansion under this family rather than creating a
   second spatial root
