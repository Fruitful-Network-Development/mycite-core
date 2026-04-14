# Route Model

Canonical visible routes:

- `/portal/system`
- `/portal/system/operational-status`
- `/portal/system/tools/<tool_slug>`
- `/portal/network`
- `/portal/utilities`
- `/portal/utilities/tool-exposure`
- `/portal/utilities/integrations`

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

Runtime returns the canonical route and canonical query projection in every reducer-owned envelope. The browser updates history only from that runtime-returned canonical URL.
