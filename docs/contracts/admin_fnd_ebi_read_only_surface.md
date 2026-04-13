# Admin FND-EBI Read-Only Surface

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This document defines the current V2 wire contract for the admin `FND-EBI`
read-only tool surface.

## Ownership

- shell legality, routing, and admin-band placement are owned by
  `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py`
- runtime composition is owned by
  `MyCiteV2/instances/_shared/runtime/admin_fnd_ebi_runtime.py`
- filesystem profile and hosted-site visibility reads are owned by
  `MyCiteV2/packages/adapters/filesystem/fnd_ebi_read_only.py`
- client JS renders the server-composed profile and file-state projection; it
  does not infer hosted-site authority on its own

## Registry And Entrypoint

- `tool_id`: `fnd_ebi`
- `tool_kind`: `service_tool`
- `slice_id`: `admin_band6.fnd_ebi_read_only_surface`
- `entrypoint_id`: `admin.fnd_ebi.read_only`
- request schema: `mycite.v2.admin.fnd_ebi.read_only.request.v1`
- surface schema: `mycite.v2.admin.fnd_ebi.read_only.surface.v1`
- workbench kind: `fnd_ebi_workbench`
- inspector kind: `fnd_ebi_summary`
- config gate: `tool_exposure.fnd_ebi.enabled`

## Read Boundary

- profiles are loaded from `private/utilities/tools/fnd-ebi/`
- canonical live profile schema is `mycite.service_tool.fnd_ebi.profile.v1`
- the stable profile minimum is:
  - `domain`
  - `site_root`
- the hosted client root is derived from `site_root.parent`
- reads stay bounded under `webapps/clients/<domain>/analytics/`
- the current slice reads:
  - `nginx/access.log`
  - `nginx/error.log`
  - `events/YYYY-MM.ndjson`
- legacy `analytics/evnts/YYYY-MM.ndjson` remains compatibility-read only when
  the canonical file is absent

## Request Shape

Required fields:

- `schema`
- `tenant_scope`

Optional fields:

- `shell_chrome`
- `selected_domain`
- `year_month`

`selected_domain` must be a plain domain-like token.

`year_month` must use `YYYY-MM`.

## Surface Payload

The surface payload contains:

- `profile_cards`
- `selected_domain`
- `overview`
- `traffic`
- `events_summary`
- `errors_noise`
- `files`
- `selected_profile`
- `year_month`
- `warnings`

`files.<source>.state` may be:

- `ready`
- `missing`
- `unreadable`
- `empty`
- `no_events_written`
- `unavailable`

## Immediate implementation rule

- keep `FND-EBI` under `Utilities`
- keep the first slice read-only and profile-led
- do not split analytics/site visibility into a separate root tool
- do not revive `tenant_progeny_profiles` or placeholder hosted workbench
  surfaces inside the live runtime
