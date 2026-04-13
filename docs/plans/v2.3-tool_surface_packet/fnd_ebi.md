# FND-EBI

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Canonical name: `FND-EBI`\
Packet role: `family_root`\
Queue posture: `near-term candidate`\
Primary future gate target: `tool_exposure.fnd_ebi`

## Completion intent

`FND-EBI` is the single service-and-site operational visibility family for
hosted websites and related service profiles.

It is:

- profile-led
- filesystem-backed through bounded internal-source reads
- shared-core derived
- read-only first

It is not the web design tool. Analytics and site-operations visibility belong
here; design/editing belongs in `FND-DCM`.

## Current code, docs, and live presence

- Current code: no V2 `fnd_ebi` registry entry or runtime entrypoint exists.
- Legacy evidence: V1 service-tool mediation docs, tests, utility-state files,
  and profile-led internal file source rules still exist.
- Live presence: FND still has `private/utilities/tools/fnd-ebi/` and
  `data/sandbox/fnd-ebi/sources/`; TFF does not.

## Stable data roots

Canonical profile input includes at minimum:

- `domain`
- `site_root`

From that, the analytics root is derived.

For a hosted site under `/srv/webapps/clients/<domain>/`, the operational
analytics root should be treated as `/srv/webapps/clients/<domain>/analytics/`.

Stable read families under that root are:

- `events/`
- `nginx/`

`analytics` is therefore a child capability direction under `FND-EBI`, not a
separate root tool.

## Next actual slice under this family

The first implementation slice should be one read-only admin-first
service-profile and analytics visibility surface.

It should:

- load one service profile
- derive analytics roots from `site_root`
- read `nginx/` and `events/`
- render overview, traffic, events, errors/noise, and file-state summaries
- surface missing, unreadable, and stale conditions explicitly

## Do not carry forward

Do not carry forward:

- a separate analytics dashboard root
- a separate generic operations dashboard root
- raw unrestricted filesystem authority
- V1 tool mediation or config-driven mounting
