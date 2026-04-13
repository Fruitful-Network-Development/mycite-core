# Decision Record 0013: Tool Taxonomy And Network Contract-First Sequence

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

Date: 2026-04-13

## Status

Accepted.

## Context

V2 already established the correct shell/root posture and the dual-gate
`tool_exposure` model, but repo truth still drifted in three places:

- tool taxonomy still carried legacy `default tool` language
- the implemented spatial slice still used `maps` as the canonical V2 name
- hosted/progeny/network planning remained mostly legacy evidence instead of a
  contract-first V2 sequence

## Decision

1. Shell roots remain shell roots.

- `System`, `Network`, and `Utilities` remain `root_service` navigation items.
- Root services are not tools and must not be serialized as tools.

2. V2 tool taxonomy is explicit.

- Every shell-owned tool descriptor and tool runtime entrypoint now carries
  `tool_kind`.
- Allowed values are:
  - `general_tool`
  - `service_tool`
  - `host_alias_tool`
- `default_tool` is forbidden vocabulary in forward V2 contracts and code.

3. Spatial family naming is canonicalized now.

- The implemented spatial family is `CTS-GIS`.
- Canonical live ids are `tool_id=cts_gis`,
  `slice_id=admin_band5.cts_gis_read_only_surface`,
  `entrypoint_id=admin.cts_gis.read_only`, and
  `/portal/utilities/cts-gis`.
- Legacy sandbox datum evidence under `data/sandbox/maps/**` remains archival or
  compatibility evidence only.

4. Chronology is mediation, not a tool family in the active queue.

- `Calendar` does not receive a live V2 `tool_id`.
- `tool_exposure.calendar` is not part of the forward contract.
- Chronology is treated as HOPS-governed mediation that may render through
  shell/interface-panel surfaces after a later slice approval.

5. Hosted/network work stays contracts-first.

- No host-alias runtime or progeny workspace implementation resumes until the
  hosted/network contracts are approved.
- `/portal/network` remains intentionally lightweight and points operators to
  the contract-governed sequence rather than a placeholder provider family.

## Consequences

- Shell/tool contracts, runtime catalogs, docs, and tests must use
  `tool_kind`.
- `CTS-GIS` replaces `Maps` as the forward V2 name in code, routes, docs, and
  tests.
- Calendar planning moves out of the active tool packet and into chronology
  mediation contracts.
- Hosted/progeny follow-on work begins with `portal_instance`, `host_alias`,
  `progeny_link`, `p2p_contract`, and `external_service_binding` contracts.
