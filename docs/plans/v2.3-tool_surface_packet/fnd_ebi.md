# FND-EBI

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Canonical name: `FND-EBI`\
Packet role: `family_root`\
Queue posture: `implemented family root`\
Primary live gate target: `tool_exposure.fnd_ebi`

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

- Current code: V2 now has a shell-owned `fnd_ebi` registry entry, the
  `admin.fnd_ebi.read_only` runtime entrypoint, and the canonical route
  `/portal/utilities/fnd-ebi`.
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

## Implemented first slice under this family

The first implementation slice is one read-only admin-first service-profile and
hosted-site visibility surface.

It now:

- loads one or more service profiles
- derives analytics roots from `site_root`
- reads `nginx/` and `events/`
- renders overview, traffic, events, errors/noise, and file-state summaries
- surfaces missing, unreadable, stale, and legacy-path conditions explicitly

See:

- [../../contracts/admin_fnd_ebi_read_only_surface.md](../../contracts/admin_fnd_ebi_read_only_surface.md)
- [../post_mvp_rollout/admin_first/fnd_ebi_read_only_surface.md](../post_mvp_rollout/admin_first/fnd_ebi_read_only_surface.md)

## Do not carry forward

Do not carry forward:

- a separate analytics dashboard root
- a separate generic operations dashboard root
- raw unrestricted filesystem authority
- V1 tool mediation or config-driven mounting
