# V3.4.3 CTS-GIS Hanus Lens Completion Audit

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This audit records the completion pass that moved CTS-GIS from
interface-panel-primary posture only to interface-panel-primary operation.

## Why this audit exists

After the V3.4.2 shell-posture realignment, CTS-GIS opened the inspector as the
primary surface, but the dominant GeoJSON and mediation controls still lived in
the workbench renderer. That left the shell contract and the actual operator
surface partially out of alignment.

## Completion outcome

- the inspector kind is now `cts_gis_interface_panel`
- the dominant interface panel now owns the GeoJSON lens, attention shell,
  intention controls, lens toggles, and concise operator focus
- the workbench remains mounted as secondary evidence context for document
  switching, diagnostics, projected-feature tables, selected-row evidence, and
  raw datum underlay inspection
- both shell regions continue to render from the same canonical
  `surface_payload`
- the browser still dispatches only through
  `POST /portal/api/v2/admin/cts-gis/read-only`

## Boundaries preserved

- no new root service, no tenant-facing CTS-GIS expansion, and no V1 route
  revival
- `intention_token` remains opaque to the client; the documented server-issued
  shapes remain `0`, `1-0`, and `branch:<node_id>`
- HOPS decoding and GeoJSON derivation remain server-side in CTS-GIS mediation
- SAMRAS remains traversal/profile authority, not geometry authority
- live exposure remains FND-first while shared portal deployment still updates
  both FND and TFF portal builds

## Supersession note

This audit follows
[v3_4_2_ui_hydration_and_alignment_audit_2026-04-13.md](v3_4_2_ui_hydration_and_alignment_audit_2026-04-13.md)
and resolves the remaining summary-first inspector drift for CTS-GIS.
