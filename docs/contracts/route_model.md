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
- `POST /portal/api/v2/system/tools/aws`
- `POST /portal/api/v2/system/tools/aws-narrow-write`
- `POST /portal/api/v2/system/tools/aws-csm-sandbox`
- `POST /portal/api/v2/system/tools/aws-csm-onboarding`
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
- tool pages reuse the same query keys, but runtime remains the source of truth

Within `file=anthology`, the workbench may render layered datum-table groupings and a selected-datum inspector lens, but those are projections of the same reducer-owned SYSTEM state.

Runtime returns the canonical route and canonical query projection in every reducer-owned envelope. The browser updates history only from that runtime-returned canonical URL.

NETWORK root query projection keys:

- `view`
- `contract`
- `type`
- `record`

NETWORK root canonical query rules:

- fresh `NETWORK` entry projects `view=system_logs`
- `contract=<contract_id>` narrows the same workbench to contract correspondence
- `type=<event_type_id>` narrows the same workbench to one event type
- `record=<datum_address>` focuses one log row in the read-only inspector

`NETWORK` is not a tool and not a sandbox. It has no canonical Messages, Hosted, Profile, or Contracts child-tab route model in V2.
