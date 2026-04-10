# Hosted Sessions And Alias Shell

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Network And Hosted](README.md)

## Status

Canonical

## Parent Topic

[Network And Hosted](README.md)

## Current Contract

Hosted sessions are derived from build-seeded and runtime-normalized hosted metadata plus contracts and progeny instances.

Current flow is:

1. build spec seeds hosted payload, contracts, and progeny templates or instances
2. materialization writes `private/network/hosted.json` and related state
3. alias navigation selects the alias, contract, and progeny type
4. the hosted model resolves the correct template and interface
5. the hosted shell renders tabs and layouts from that interface
6. page handlers load actual data through contracts, profile refs, anthology, and public metadata

The shell chooses which hosted page to render. It does not implement inheritance or contract logic itself.

Alias and hosted shells remain layout and navigation layers over the underlying relationship and data models.

## Boundaries

This page owns hosted-session derivation and alias-shell framing. It does not own:

- contract compact-array semantics
- public profile-card schema
- local anthology mutation rules
- `SYSTEM` page composition

## Authoritative Paths / Files

- `docs/HOSTED_SESSIONS.md`
- `docs/HOSTED_SHELL_ALIAS.md`
- hosted model and alias shell code under `instances/_shared/portal/**`

## Source Docs

- `docs/HOSTED_SESSIONS.md`
- `docs/HOSTED_SHELL_ALIAS.md`
- `docs/PORTAL_BUILD_SPEC.md`

## Update Triggers

- Changes to hosted.json derivation
- Changes to alias-to-progeny resolution
- Changes to hosted template or layout selection
- Changes to page-handler versus shell responsibility
