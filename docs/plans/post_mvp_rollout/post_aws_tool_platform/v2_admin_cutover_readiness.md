# V2 Admin Cutover Readiness

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This file states the current cutover posture for MyCiteV2 as the operational
admin portal base.

Use [v2_native_cutover_hardening.md](v2_native_cutover_hardening.md) for the
active remaining work. This file is a posture reference, not the main work
queue.

There are three readiness levels:

- platform readiness: V2 admin shell, registry, runtime envelope, AWS read-only, and AWS narrow-write are implemented and tested
- deployment readiness: the live `/portal` boundary reaches those V2 runtime entrypoints through an approved V2 deployment shape
- hardening readiness: the live deployment contract, auth boundary, smoke coverage, and V1 retirement review are explicit and current

## Cutover statement

MyCiteV2 is platform-ready as the stable admin portal base when:

- `admin.shell_entry` is the intended admin landing path
- shell-owned registry descriptors are the only tool launch surface
- runtime entrypoints are cataloged in `runtime_platform.py`
- Admin Band 0 remains green
- AWS read-only remains green
- AWS narrow-write remains green
- old provider-admin routes are not used as v2 entry surfaces

MyCiteV2 is deployment-ready when:

- the live `/portal` route reaches approved V2 runtime entrypoints through the current V2 host shape
- [live_state_authority_and_mapping.md](live_state_authority_and_mapping.md) is implemented for any live AWS exposure
- the live `/portal` route can reach V2 runtime entrypoints without root compatibility links

MyCiteV2 is hardening-ready when:

- deployment shape, ports, env contract, and rollback are repo-owned or explicitly contract-defined
- auth and audience enforcement are documented and tested
- black-box smoke checks exist for the deployed portal boundary
- V1 retention vs retirement is recorded explicitly

## Operational replacement rule

The old portal is displaced slice by slice.

Allowed:

- use v1 as operational evidence
- expose v2 admin landing and AWS slices where gates pass
- add future tools through the drop-in contract

Forbidden:

- route-level parity porting
- direct provider-admin fallback routes
- standalone `newsletter-admin`
- broad mixed provider dashboards
- flavor-specific copies of shared runtime entrypoints

## Deployment-facing checklist

- run the full post-AWS regression stack
- verify no dynamic registry scanning exists
- verify no provider secrets appear in runtime payloads
- verify unknown tools are denied by shell-owned launch policy
- verify Maps and AGRO-ERP are absent until their own slices are approved
- verify the live V2 host shape is explicit and tested
- verify no root-level compatibility symlinks are needed
- verify live AWS writes use one canonical live artifact
- verify auth and audience denial behavior at the deployed edge
- verify the hardening items in [v2_native_cutover_hardening.md](v2_native_cutover_hardening.md) remain accurate

## Current cutover posture

Current status: platform-ready and deployment-ready through the V2-native portal
host for FND and TFF.

V2 `admin.shell_entry` is reached through the live V2 portal host rather than
through a bridge-owned live boundary.

Trusted-tenant AWS exposure reads and writes the configured canonical live AWS
profile JSON through the V2 live profile adapter.
`MYCITE_V2_AWS_STATUS_FILE` must point at the approved live `aws-csm.*.json`
profile for each deployed portal service.

Shape B bridge work remains historical cutover evidence only.

The remaining cutover work is hardening and clarity work, not shared-platform
redesign.
