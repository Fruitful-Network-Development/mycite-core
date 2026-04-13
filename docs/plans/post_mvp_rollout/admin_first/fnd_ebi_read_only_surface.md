# FND-EBI Read-Only Surface

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This file records the first implemented `FND-EBI` slice after the AWS-first and
CTS-GIS groundwork.

## Slice identity

- band: `Admin Band 6 Internal FND-EBI Read-Only`
- slice id: `admin_band6.fnd_ebi_read_only_surface`
- entrypoint id: `admin.fnd_ebi.read_only`
- canonical route: `/portal/utilities/fnd-ebi`
- config gate: `tool_exposure.fnd_ebi`

## What the implemented slice does

- reads `mycite.service_tool.fnd_ebi.profile.v1` files from
  `private/utilities/tools/fnd-ebi/`
- derives the hosted analytics root from `site_root`
- reads bounded hosted-site evidence from:
  - `analytics/nginx/access.log`
  - `analytics/nginx/error.log`
  - `analytics/events/YYYY-MM.ndjson`
- renders:
  - per-profile cards
  - overview and file-state summaries
  - traffic and event counts
  - error/noise summaries
  - explicit missing, unreadable, stale, and legacy-path warnings

## What this slice does not do

- it does not write hosted-site or provider state
- it does not treat analytics as a separate tool family
- it does not load host aliases, progeny links, or P2P contract work into the
  live surface
- it does not replace later `FND-DCM` design/content work

## Immediate follow-on constraints

- later `FND-EBI` work may expand detail and summaries, but must stay
  profile-led and bounded
- hosted/network entity work still starts from
  `docs/contracts/host_alias_and_portal_instance_contract.md`
- future `FND-EBI` slices must keep shell-owned launch legality and
  `tool_exposure` gating intact
