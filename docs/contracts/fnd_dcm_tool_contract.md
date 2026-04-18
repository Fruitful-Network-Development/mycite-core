# FND-DCM Tool Contract

`FND-DCM` is the canonical read-only hosted-manifest inspection tool under `SYSTEM`.

Canonical public route:

- `/portal/system/tools/fnd-dcm`

Canonical direct API:

- `POST /portal/api/v2/system/tools/fnd-dcm`
- request schema: `mycite.v2.portal.system.tools.fnd_dcm.request.v1`
- surface schema: `mycite.v2.portal.system.tools.fnd_dcm.surface.v1`

The tool is runtime-owned and query-driven.

Canonical query keys:

- `site`
- `view`
- `page`
- `collection`

Canonical fresh entry:

- `site=cuyahogavalleycountrysideconservancy.org&view=overview`

Canonical view rules:

- `view=overview` shows normalized site, navigation, footer, page, and collection counts
- `view=pages` may project `page=<page_id>`
- `view=collections` may project `collection=<collection_id>`
- `view=issues` projects normalized manifest and collection issues

Runtime owns canonical selection cleanup:

- when `view` is not `pages`, runtime clears `page`
- when `view` is not `collections`, runtime clears `collection`
- when the selected `site` changes and the current `page` or `collection` is invalid for that site, runtime clears the stale key

Posture rules:

- `FND-DCM` is interface-panel-led
- its workbench is hidden by default
- the workbench is reserved for raw manifest JSON, collection file metadata, and normalization evidence
- v1 is inspection and normalization only; no draft, publish, or write route exists

Operational gating:

- `FND-DCM` requires `fnd_peripheral_routing`
- `FND-DCM` requires `hosted_site_manifest_visibility`
- `FND-DCM` requires `webapps_root` for operational status
- the tool may remain visible while `operational=false`

Profile root:

- `private/utilities/tools/fnd-dcm/`

Each profile declares:

- `schema`
- `domain`
- `label`
- `manifest_relative_path`
- `render_script_relative_path`

All profile-relative paths resolve from:

- `webapps_root/clients/<domain>/frontend`

Absolute request-supplied paths are not part of the contract.
