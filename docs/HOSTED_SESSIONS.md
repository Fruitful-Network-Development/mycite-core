## Hosted sessions, contracts, and progeny

This note explains how **hosted sessions** are derived from contracts and progeny in the current FND/TFF model. It is intentionally generic so other legal‑entity portals can reuse the same pattern.

### 1. Build spec → hosted.json

- Each portal has a repo‑owned build spec (for example `[portals/mycite-le_fnd/build.json]`).
- The build spec is authoritative for:
  - `private/config.json`
  - `private/network/hosted.json`
  - seeded `private/network/contracts/*.json`
  - seeded `private/network/progeny/*.json`
- On materialize, the `hosted` section of the build spec becomes `private/network/hosted.json`, which is then normalized by `portal.hosted_model.normalize_hosted_payload`.

For FND, the hosted payload:

- uses `type: "subject_congregation"` with a `google_classroom_reference` style
- defines:
  - `type_values.default_hosted` (maps top‑level tabs like `stream`, `classwork`, `people`/`discover`, `workflow` to JSON payloads)
  - `subject_congregation.tabs` (tab ids, labels, descriptions)
  - `broadcaster` (public pages such as `stream`, `discover`, `calendar`, `workflow`)
  - `progeny.templates.*.hosted_interface` (per‑progeny layout and tabs)

`portal.hosted_model` provides defaults and merging rules so each portal can override just the parts it needs.

### 2. Contracts and progeny instances

#### Seeded contracts

The build spec seeds:

- a **member_alias_profile** contract (e.g. `contract-fnd-tff-member-001`)
- a **portal_demo_contract** contract

These contracts live under `private/network/contracts/*.json` and carry:

- `owner_msn_id` (host portal MSN)
- `counterparty_msn_id` (client portal MSN)
- `details.hosted_layout` (e.g. `classroom_orientation`)

#### Progeny instances

The build spec also seeds progeny instances under `private/network/progeny/*.json`. For FND:

- each member progeny instance payload includes:
  - `profile_type: "member"`
  - `contract.contract_id` and `contract_refs.authorization_contract_id`
  - `hosted_interface` (layout + tabs)
  - `alias_profile.host_portal` and `alias_profile.alias_id`

The **contract** is therefore the durable link between:

- the host portal’s MSN
- the client portal’s MSN
- the progeny instance used for the hosted session

### 3. Alias session → hosted interface

When a user navigates to `/portal/alias/<alias_id>` on FND:

- the runtime (see `runtime/flavors/fnd/app.py`) loads the alias record under `private/network/aliases/**`
- that alias record includes:
  - `progeny_type` (e.g. `member`)
  - `contract_id` for the member alias profile
  - `workspace_layout` / `hosted_layout` hint
- the alias shell delegates to the **hosted model**:
  - it resolves the correct progeny template for the given `progeny_type` using `portal.hosted_model.get_progeny_template(read_hosted_payload(private_dir), progeny_type)`
  - it uses the template’s `hosted_interface` (layout + default tab + tabs) to drive which subject‑congregation tabs are available in the UI

Per‑instance progeny files may override parts of the template (for example `hosted_interface.layout`), but the canonical default behavior lives in `private/network/hosted.json` and is edited via the **Progeny** utilities workbench.

### 4. Reference inheritance and hosted pages

Hosted pages (subject‑congregation tabs and broadcaster pages) may rely on:

- contract context (MSS compact array) to interpret foreign datums
- local anthology rows for hosted analytics or event feeds
- public contact‑card exported datums

The shell does not implement inheritance logic itself; instead:

- it selects **which page** to render (stream, discover, calendar, workflow) based on `hosted_interface` and `hosted.json`
- the page’s backend handler (e.g. workflow analytics, discovery search) uses the contract id, MSN ids, and profile refs from the progeny instance to:
  - resolve the correct contract
  - resolve foreign datums via MSS
  - resolve public datums via contact cards

This keeps the hosting shell generic: it only knows about **tabs and layouts**, not how data inheritance is implemented.

### 5. Session model (summary)

Putting it together:

1. **Build spec** seeds contracts, hosted layout, and progeny templates/instances.
2. **Materialization** writes `private/network/hosted.json`, contracts, progeny instances, and alias records.
3. **Alias navigation** (`/portal/alias/<alias_id>`) picks the alias, its contract, and its progeny type.
4. **Hosted model** selects the progeny template and its `hosted_interface` from `hosted.json`.
5. **Subject‑congregation shell** renders tabs and routes based on `hosted_interface` and `hosted.subject_congregation`.
6. **Page handlers** (stream, discover, calendar, workflow) use contracts + profile refs + anthology + public metadata to load their data, without hard‑coding FND‑only semantics into the shell.

This is the pattern future legal‑entity portals and subject‑congregation styles should follow: contracts identify the relationship, progeny instances capture per‑member configuration, and `hosted.json` + hosted model define how a session is presented.

