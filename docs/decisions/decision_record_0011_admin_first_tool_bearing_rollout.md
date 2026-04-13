# ADR 0011: Admin-First Tool-Bearing Rollout

## Status

Accepted

## Context

The MVP proves the architecture and the post-MVP rollout docs define generic slice rollout, but they do not yet externalize how the old portal should be operationally replaced in a tool-bearing way. Without an explicit admin-first track, future agents are likely to recreate v1 portal drift by mixing shell, provider dashboards, tool launch, and runtime routing again.

## Decision

The operational replacement path is admin-first.

That means:

- first build one stable admin shell entry
- then one tenant-safe admin runtime envelope
- then one admin home/status surface
- then one tool registry/launcher surface
- then AWS as the first real tool-bearing target
- then CTS-GIS
- then AGRO-ERP

The authoritative docs for this track are the files under [../plans/post_mvp_rollout/admin_first/](../plans/post_mvp_rollout/admin_first/).

## Consequences

- Old portal replacement proceeds by narrow admin slices rather than by parity-porting routes or packages.
- Tools remain shell-attached and runtime-cataloged.
- AWS becomes the first tool-bearing target because it is the narrowest high-value operational slice with explicit v1 correction guidance.
- Standalone `newsletter-admin` remains retired.
- CTS-GIS and AGRO-ERP are protected from being pulled forward through convenience.
