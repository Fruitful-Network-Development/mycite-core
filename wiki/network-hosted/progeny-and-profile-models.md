# Progeny And Profile Models

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Network And Hosted](README.md)

## Status

Canonical

## Parent Topic

[Network And Hosted](README.md)

## Current Contract

Canonical relationship terminology uses `member`, with legacy aliases such as `tenant` and `board_member` kept readable during migration.

Baseline legal-entity type expectations include:

- `poc`
- `member`
- `user`

Current progeny direction is:

- canonical runtime config in `private/config.json`
- canonical progeny instance storage under `private/network/progeny/`
- default type templates in `private/network/hosted.json -> progeny.templates`

Profile cards are metadata-only relationship views. They are JSON-backed and must not contain secrets or credentials.

Current non-secret member integration metadata may include:

- PayPal profile and checkout routing refs
- AWS profile and emailer refs
- website analytics metadata
- forwarder-only email policy metadata

These fields are metadata pointers and policy hints only. Runtime credentials and provider state remain outside profile-card and progeny metadata.

Profile-card sources may include config refs, internal JSON, alias-derived data, or migration outputs, but cards are deduplicated by `progeny_id`.

## Boundaries

This page owns progeny terminology, instance direction, and profile-card framing. It does not own:

- hosted shell layout selection
- NETWORK contract editor semantics
- secrets or operational credentials
- general runtime config canonicalization beyond progeny scope

## Authoritative Paths / Files

- `docs/PROGENY_CONFIG_MODEL.md`
- `docs/PROGENY_PROFILE_CARDS.md`
- `private/network/progeny/`
- `private/network/hosted.json`

## Source Docs

- `docs/PROGENY_CONFIG_MODEL.md`
- `docs/PROGENY_PROFILE_CARDS.md`
- `docs/HOSTED_SESSIONS.md`
- `docs/AWS_EMAILER_ABSTRACTION.md`
- `docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md`

## Update Triggers

- Changes to canonical progeny terminology
- Changes to instance-storage direction
- Changes to profile-card schema or allowed sources
- Changes to secret-handling or metadata boundary rules
