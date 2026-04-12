# FND-EBI

Canonical name: `FND-EBI`  
Working expansion: `FND External/Entity Business Intelligence`  
Tool family posture: `carry_forward as one V2.3 tool family`  
Primary exposure: `internal-admin` first  
Primary read/write posture: `read-only first`

## 1. Completion intent

`FND-EBI` is the single service-and-site operational visibility tool for hosted websites and related service profiles.

Its primary data posture is:

- profile-led
- shared-core derived
- filesystem-backed through bounded internal-source reads
- read-only first

This is the analytics and site-operations tool. It is not the web design tool.

## 2. Source basis

Repo sources investigated:

- `docs/plans/v2.3-tool_surface_packet/fnd_ebi.md`
- `docs/wiki/legacy/tools/internal-file-sources.md`
- `docs/wiki/legacy/tools/member-service-integrations.md`
- `docs/contracts/legacy/analytics.md`
- `docs/contracts/tool_exposure_and_admin_activity_bar_contract.md`
- `docs/plans/post_mvp_rollout/post_aws_tool_platform/future_tool_drop_in_contract.md`

The strongest file-root guidance comes from `internal-file-sources.md`, which defines the profile-led derivation of analytics paths from `site_root`.

## 3. Core V2.3 position

`FND-EBI` should complete as one read-oriented service visibility family.

It should not be split into:

- a separate analytics dashboard root
- a separate generic operations dashboard root
- a raw file-browser root

Instead, `FND-EBI` should be the one tool that answers:

- what site or domain is this
- what service/profile state governs it
- what do the live logs and events say
- what warnings or operator signals exist right now

## 4. Stable data roots

The investigated docs support a profile-led derivation model.

Canonical profile input includes at minimum:

- `domain`
- `site_root`

From that, the analytics roots are derived.

For a hosted site under:

`/srv/webapps/clients/<domain>/`

the operational analytics root should be treated as:

`/srv/webapps/clients/<domain>/analytics/`

Inside that root, the stable read families are:

- `events/`
- `nginx/`

The concrete log files expected by the investigated legacy docs are:

- `analytics/nginx/access.log`
- `analytics/nginx/error.log`
- `analytics/events/YYYY-MM.ndjson`

This matches your described directory posture: one analytics root with `events/` and `nginx/`.

## 5. Required read model

The first complete `FND-EBI` surface should reconstruct operational visibility from the profile and derived analytics roots.

It should provide the following bounded read domains:

### 5.1 Overview
- profile identity
- domain
- site root
- analytics root
- freshness summary
- warnings

### 5.2 Traffic
- recent volume windows
- approximate unique visitors
- response-class breakdown
- asset-vs-page request split
- top pages and referrers

### 5.3 Events
- event file presence
- recent event counts
- event type counts
- stale/missing event warnings

### 5.4 Errors / Noise
- top error routes
- suspicious probes
- bot/crawler separation where detectable
- noisy-path summaries

### 5.5 Files
- file-presence and readability checks
- last-seen timestamps where parseable
- bounded visibility into current source files

## 6. Completion slices

### Slice 1 — read-only service profile and analytics visibility
This is the first required completion slice.

It should:

- load one service profile
- derive analytics roots from `site_root`
- read `nginx/` and `events/`
- render Overview, Traffic, Events, Errors/Noise, and Files
- explicitly surface missing/unreadable/stale conditions

### Slice 2 — service integration overlays
Later read-only expansion.

May include:

- registrar state
- service metadata
- domain posture
- integration warnings

### Slice 3 — narrow actions
Only later, and only if a distinct action authority is defined.

Examples could include bounded refresh or reconciliation actions, but those are out of scope for initial completion.

## 7. Do not carry forward

Do not carry forward:

- raw unrestricted filesystem authority
- broad generic operations-workbench semantics
- config-driven mounting
- analytics path logic duplicated in tool-local code
- a separate standalone analytics root tool

## 8. Acceptance boundary

`FND-EBI` is complete when one approved read-only slice can:

- load profile-backed service/site state
- derive analytics roots deterministically
- read from `/srv/webapps/clients/<domain>/analytics/`
- use `events/` and `nginx/` as stable source families
- render operator summaries and warnings
- remain one tool, not a split analytics/operations family

## 9. Recommended V2.3 landing statement

Treat `FND-EBI` as one profile-led operational visibility tool whose stable source families live under each client site's `analytics/` root. Any later analytics-specific reporting belongs as a child slice of `FND-EBI`, not as a second root tool.
