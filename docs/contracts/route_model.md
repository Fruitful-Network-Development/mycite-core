# Route Model

Canonical visible routes:

- `/portal`
- `/portal/system`
- `/portal/system/tools/<tool_slug>`
- `/portal/system/tools/workbench-ui`
- `/portal/network`
- `/portal/utilities`
- `/portal/utilities/tool-exposure`
- `/portal/utilities/integrations`

`/portal` is the canonical public entry and redirects to `/portal/system`.

`/portal/system` opens the SYSTEM datum-file workbench. Its fresh reducer-owned entry projects the system sandbox anchor file, `anthology.json`.

For migrated portals, the authoritative `SYSTEM` datum/workbench/profile/grant posture is resolved from the MOS authority database. Missing or uninitialized SQL authority is a readiness failure rather than a filesystem fallback for those migrated surfaces.

`/portal/network` opens the read-only NETWORK system-log workbench. Its canonical operational document is `data/system/system_log.json`. Contract correspondence is selected as a filter over the same document rather than through peer tabs or child routes.

Former dedicated activity and profile-basics leaf pages are gone. Those views now project through `/portal/system` workspace state with `file=activity` and `file=profile_basics`.

Canonical shell API:

- `POST /portal/api/v2/shell`

Direct APIs:

- `POST /portal/api/v2/system/workspace/profile-basics`
- `POST /portal/api/v2/system/tools/workbench-ui`
- `POST /portal/api/v2/system/tools/aws-csm`
- `POST /portal/api/v2/system/tools/aws-csm/actions`
- `POST /portal/api/v2/system/tools/cts-gis`
- `POST /portal/api/v2/system/tools/fnd-dcm`
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

AWS-CSM internal action route:

- `POST /portal/api/v2/system/tools/aws-csm/actions`
- request schema: `mycite.v2.portal.system.tools.aws_csm.action.request.v1`
- body fields:
  - `portal_scope`
  - `surface_query`
  - optional `shell_state`
  - `action_kind`
  - `action_payload`
- cataloged action kinds:
  - `create_profile`
  - `stage_smtp_credentials`
  - `send_handoff_email`
  - `reveal_smtp_password`
  - `refresh_provider_status`
  - `capture_verification`
  - `confirm_verified`

`AWS-CSM` is one `SYSTEM` child service tool surface, not four separate tool pages. The canonical public route is `/portal/system/tools/aws-csm`.

`FND-DCM` is one `SYSTEM` child service tool surface. The canonical public route is `/portal/system/tools/fnd-dcm`.

FND-DCM tool query projection keys:

- `site`
- `view`
- `page`
- `collection`

FND-DCM canonical query rules:

- fresh `FND-DCM` entry projects `site=cuyahogavalleycountrysideconservancy.org&view=overview`
- `view=pages` may project `page=<page_id>`
- `view=collections` may project `collection=<collection_id>`
- runtime clears stale `page` and `collection` selections when `site` or `view` changes

`Workbench UI` is one `SYSTEM` child SQL authority-inspection surface. The canonical public route is `/portal/system/tools/workbench-ui`.

It does not replace `/portal/system`, and it does not imply coverage of retained host-bound/private assets or `NETWORK` derived materializations.

Workbench UI query projection keys:

- `document`
- `document_filter`
- `document_sort`
- `document_dir`
- `filter`
- `sort`
- `dir`
- `group`
- `workbench_lens`
- `source`
- `overlay`
- `row`

Workbench UI canonical query rules:

- fresh `Workbench UI` entry prefers the first available `sandbox:cts_gis:*` document in the current document-table ordering and falls back to the first available authoritative document when no CTS-GIS document is present; the default fresh query still projects `document_sort=version_hash&document_dir=asc&sort=datum_address&dir=asc&group=flat&workbench_lens=interpreted&source=show&overlay=show`, plus the first selected row from that resolved document
- `document=<document_id>` selects one SQL-backed authoritative document
- `document_filter=<text>` narrows the read-only document table by `document_id`, `document_name`, `source_kind`, or `version_hash`
- `document_sort=<document_id|document_name|source_kind|row_count|version_hash>` changes document-table ordering
- `document_dir=<asc|desc>` changes document-table order direction
- `filter=<text>` narrows the selected-document row grid, including `hyphae_hash`
- `sort=<datum_address|layer|value_group|iteration|labels|relation|object_ref|hyphae_hash>` changes flat row-grid ordering
- `dir=<asc|desc>` changes row-grid order direction
- `group=<flat|layer|layer_value_group>` switches the datum grid between flat and structural grouping modes while grouped sections preserve canonical structural order
- `workbench_lens=<interpreted|raw>` switches the workbench between the interpreted row summary and the raw canonical payload lens
- `source=<show|hide>` toggles source metadata columns and sections without changing authoritative rows
- `row=<datum_address>` focuses one selected row in the read-only Interface Panel detail view
- `overlay=hide` suppresses additive directive summaries without changing authoritative row content
- keyboard navigation and next/previous selection actions stay query-driven by resolving to canonical `document` and `row` selections rather than adding new navigation keys

`CTS-GIS` is one `SYSTEM` child mediation tool surface. The canonical public route is `/portal/system/tools/cts-gis`.

CTS-GIS request body contract:

- shared shell query stays unchanged
- tool-local state is carried in `tool_state`
- runtime mode is explicit in body via `runtime_mode`:
  - `production_strict`
  - `audit_forensic`
- CTS-GIS canonical `tool_state` keys are:
  - `tool_state.active_path`
  - `tool_state.selected_node_id`
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
- `Diktataograph` is projected through `navigation_canvas`
- `navigation_canvas.mode` defaults to `directory_dropdowns`
- `navigation_canvas.source_authority=samras_magnitude`
- `navigation_canvas.decode_state` is fail-closed when CTS-GIS cannot recover a valid SAMRAS structure from authority rows or legacy row reconstruction
- `navigation_canvas.dropdowns` carries one dropdown per resolved structural depth
- `navigation_canvas.active_path` carries the resolved lineage
- `Garland` is projected through `garland_split_projection`, where dominant `geospatial_projection` and secondary `profile_projection` update for that navigation root
- strict runtime also emits compact canonical models:
  - `navigation_model`
  - `projection_model`
  - `evidence_model`
- these are CTS-GIS-local projections of one mediation posture, not two separate shell mediations
- title fallback is blank-only when ASCII decoding is unavailable
- CTS-GIS supporting evidence precedence is:
  - `private/utilities/tools/cts-gis/spec.json`
  - `data/sandbox/cts-gis/tool.<msn>.cts-gis.json`
  - `data/payloads/cache/<corpus>.msn-administrative.json` for first-pass `msn-SAMRAS` authority candidates
  - `data/sandbox/cts-gis/sources/<corpus>.msn-administrative.json` for ASCII title overlays
  - GeoJSON lens or equivalent runtime cache for spatial projection
- v2.5.4 phase-B is canonical-only; CTS-GIS accepts only `cts_gis` / `cts-gis` / `sandbox:cts_gis:*` and `tool.<msn>.cts-gis.json`
- legacy CTS-GIS aliases are rejected at the CTS-GIS tool endpoint with `400 legacy_maps_alias_unsupported`
- `production_strict` runtime refuses missing/invalid compiled artifacts and returns `compiled_cts_gis_state_invalid` without request-time repair fallback

CTS-GIS canonical defaults:

- fresh entry defaults are:
- `active_path=[]`
- `selected_node_id=""`
- `attention_node_id=""`
- `intention_rule_id=descendants_depth_1_or_2`
- `time_directive=""`
- `archetype_family_id=samras_nominal`
- default supporting source document: `sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json`

CTS-GIS selection normalization:

- when the request carries `selected_node_id` or `tool_state.aitas.attention_node_id` without an explicit `tool_state.aitas.intention_rule_id`, runtime normalizes intention to `self`
- that keeps Garland aligned to the current selected node rather than inheriting the fresh-entry descendant posture
- once a node-focused attention exists, CTS-GIS round-trips widened scope as `self`, `<attention_node_id>-0`, `<attention_node_id>-0-0`, or `branch:<node_id>`
- legacy intention inputs such as `0`, `1-0`, `children`, and `descendants_depth_1_or_2` remain accepted during the compatibility phase, but returned tool state reflects the canonical resolved token
- changing tool-local intention preserves `tool_state.source.attention_document_id` unless the user explicitly selects a different source document
- Garland may materialize a blank but stateful `profile_projection` for a structurally valid selected node even when no matching profile source or HOPS geometry exists yet

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
