# Route Model

Canonical visible routes:

- `/portal`
- `/portal/system`
- `/portal/system/tools/<tool_slug>`
- `/portal/network`
- `/portal/utilities`
- `/portal/utilities/tool-exposure`
- `/portal/utilities/integrations`

`/portal` is the canonical public entry and redirects to `/portal/system`.

`/portal/system` opens the SYSTEM datum-file workbench. Its fresh reducer-owned entry projects the system sandbox anchor file, `anthology.json`.

`/portal/network` opens the read-only NETWORK system-log workbench. Its canonical operational document is `data/system/system_log.json`. Contract correspondence is selected as a filter over the same document rather than through peer tabs or child routes.

Former dedicated activity and profile-basics leaf pages are gone. Those views now project through `/portal/system` workspace state with `file=activity` and `file=profile_basics`.

Canonical shell API:

- `POST /portal/api/v2/shell`

Direct APIs:

- `POST /portal/api/v2/system/workspace/profile-basics`
- `POST /portal/api/v2/system/tools/aws-csm`
- `POST /portal/api/v2/system/tools/cts-gis`
- `POST /portal/api/v2/system/tools/fnd-ebi`

Reducer-owned query projection keys:

- `file`
- `datum`
- `object`
- `verb`

Reducer-owned canonical query rules:

- fresh `SYSTEM` entry projects `file=anthology&verb=navigate`
- sandbox-management view projects `file=sandbox&verb=navigate`
- reducer-owned tool pages reuse the same query keys, but runtime remains the source of truth

Within `file=anthology`, the workbench may render layered datum-table groupings and a selected-datum detail lens, but those are projections of the same reducer-owned SYSTEM state.

Runtime returns the canonical route and canonical query projection in every reducer-owned envelope. The browser updates history only from that runtime-returned canonical URL.

AWS-CSM tool query projection keys:

- `view`
- `domain`
- `profile`
- `section`

AWS-CSM canonical query rules:

- fresh `AWS-CSM` entry projects `view=domains`
- `domain=<domain>` focuses one domain gallery row
- `profile=<profile_id>` focuses one mailbox profile inside the selected domain
- `section=<users|onboarding|newsletter>` narrows the selected domain to one section

`AWS-CSM` is one `SYSTEM` child service tool surface, not four separate tool pages. The canonical public route is `/portal/system/tools/aws-csm`.

`CTS-GIS` is one `SYSTEM` child mediation tool surface. The canonical public route is `/portal/system/tools/cts-gis`.

CTS-GIS request body contract:

- shared shell query stays unchanged
- tool-local state is carried in `tool_state`
- CTS-GIS canonical `tool_state` keys are:
  - `tool_state.nimm_directive`
  - `tool_state.aitas.attention_node_id`
  - `tool_state.aitas.intention_rule_id`
  - `tool_state.aitas.time_directive`
  - `tool_state.aitas.archetype_family_id`
  - `tool_state.source.attention_document_id`
  - `tool_state.selection.selected_row_address`
  - `tool_state.selection.selected_feature_id`
- compatibility aliases remain accepted during the transition:
  - `mediation_state.attention_node_id`
  - `mediation_state.intention_token`
  - `selected_row_address`
  - `selected_feature_id`

CTS-GIS runtime/body rules:

- CTS-GIS is the `system.tools.cts_gis` tool_mediation_surface under `SYSTEM`
- its default posture is interface-panel-led
- the dominant Interface Panel mounts one CTS-GIS-local body with `Diktataograph` and `Garland`
- tool menubar toggles are single-click exclusive by default (`Workbench` or `Interface Panel`), with a route-scoped double-click lock that allows both
- `Diktataograph` updates CTS-GIS-local structural navigation
- `Garland` updates the correlated profile projection for that navigation root
- these are CTS-GIS-local projections of one mediation posture, not two separate shell mediations
- CTS-GIS supporting evidence precedence is:
  - `private/utilities/tools/cts-gis/spec.json`
  - `data/sandbox/cts-gis/tool.<msn>.cts-gis.json`
  - registrar payload / payload cache
  - administrative payload cache through the ASCII lens
  - GeoJSON lens or equivalent runtime cache for spatial projection
- phase-A compatibility keeps legacy `maps` storage/request identifiers loadable through one CTS-GIS compat shim and emits `cts_gis.legacy_maps_alias_consumed`
- phase-B target (v2.5.4): remove legacy `maps` alias acceptance

CTS-GIS canonical defaults:

- `attention_node_id=3-2-3-17-77`
- `intention_rule_id=descendants_depth_1_or_2`
- `time_directive=""`
- `archetype_family_id=samras_nominal`
- default supporting source document: `sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json`

NETWORK root query projection keys:

- `view`
- `contract`
- `type`
- `record`

NETWORK root canonical query rules:

- fresh `NETWORK` entry projects `view=system_logs`
- `contract=<contract_id>` narrows the same workbench to contract correspondence
- `type=<event_type_id>` narrows the same workbench to one event type
- `record=<datum_address>` focuses one log row in the read-only Interface Panel detail view

`NETWORK` is not a tool and not a sandbox. It has no canonical Messages, Hosted, Profile, or Contracts child-tab route model in V2.
