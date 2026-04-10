# Live State Authority And Mapping

Authority: [../../authority_stack.md](../../authority_stack.md)

This document defines how V2 may read and write live deployment state during the V2 admin cutover.

## Live roots

- FND live state: `/srv/mycite-state/instances/fnd/`
- TFF live state: `/srv/mycite-state/instances/tff/`
- V1 deployed mirrors: `MyCiteV1/instances/deployed/`
- V2 code and docs: `MyCiteV2/`

## Authority rule

V2 code may not create an independent operational state tree that can drift from live portal state.

During the bridge phase:

- V2 read-only surfaces must read from an explicit adapter input.
- V2 writes must target the same canonical live artifact that the read path confirms.
- V2 writes must emit local audit.
- V2 must not write hidden compatibility snapshots as if they are canonical.

## AWS mapping decision

The current V2 AWS runtime expects an AWS status snapshot shape with:

- `tenant_scope_id`
- `mailbox_readiness`
- `smtp_state`
- `gmail_state`
- `verified_evidence_state`
- `selected_verified_sender`
- `canonical_newsletter_profile`
- `compatibility`
- `inbound_capture`
- `dispatch_health`

The live V1 AWS state currently stores mailbox profiles under:

- `/srv/mycite-state/instances/fnd/private/utilities/tools/aws-csm/aws-csm.*.json`

The bridge implementation must choose exactly one mapping:

### Mapping A: Derived Read-Only Snapshot

Create an adapter that derives the V2 AWS read-only snapshot from live V1 AWS profile JSON at request time.

Allowed only for read-only exposure.

### Mapping B: Canonical V2-Compatible Profile Adapter

Create an adapter that reads and writes the canonical live AWS profile JSON directly while presenting the V2 runtime with the stable V2 status shape.

Required before exposing `admin.aws.narrow_write` against live state.

## Narrow-write authority

`admin.aws.narrow_write` may only be exposed when:

- the selected verified sender maps to one canonical live profile field
- read-after-write reads the same live artifact that was written
- the audit record includes tenant scope, profile id, updated field names, and selected sender
- failed or denied writes leave the live artifact unchanged

## FND and TFF portal mapping

The live `portal.fruitfulnetworkdevelopment.com/portal` route currently chooses the FND or TFF V1 host by cookie and nginx upstream.

The V2 deployment bridge must preserve tenant selection explicitly:

- FND shell entry uses the FND live state root.
- TFF shell entry uses the TFF live state root.
- AWS admin slices may still read FND-owned AWS tool state for tenant scopes that are operated centrally by FND.
- Cross-tenant reads must be explicit in request payloads and tests.

## Forbidden state shortcuts

- no `/srv/mycite-state/instances/*/v2` shadow authority unless a future ADR approves it
- no generated V2 AWS snapshot treated as canonical write target
- no writing both V1 profile JSON and a V2 copy
- no silently falling back from TFF to FND state root
- no root-level repo compatibility paths

## Required tests

- fixture proving live-profile-to-V2-snapshot mapping
- fixture proving FND and TFF state roots are not confused
- read-after-write against the canonical live artifact
- denied write leaves canonical live artifact unchanged
- no secret-bearing fields leak into V2 runtime payloads
