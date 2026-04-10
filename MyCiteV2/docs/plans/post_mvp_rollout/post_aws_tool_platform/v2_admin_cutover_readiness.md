# V2 Admin Cutover Readiness

Authority: [../../authority_stack.md](../../authority_stack.md)

This file defines when MyCiteV2 can be treated as the operational admin portal base.

There are two readiness levels:

- runtime readiness: V2 admin shell, registry, runtime envelope, AWS read-only, and AWS narrow-write are implemented and tested
- deployment readiness: the live `/portal` boundary reaches those V2 runtime entrypoints through an approved bridge or V2 host

## Cutover statement

MyCiteV2 is runtime-ready as the stable admin portal base when:

- `admin.shell_entry` is the intended admin landing path
- shell-owned registry descriptors are the only tool launch surface
- runtime entrypoints are cataloged in `runtime_platform.py`
- Admin Band 0 remains green
- AWS read-only remains green
- AWS narrow-write remains green
- old provider-admin routes are not used as v2 entry surfaces

MyCiteV2 is deployment-ready when:

- [deployment_bridge_contract.md](deployment_bridge_contract.md) is implemented
- [live_state_authority_and_mapping.md](live_state_authority_and_mapping.md) is implemented for any live AWS exposure
- [cutover_execution_sequence.md](cutover_execution_sequence.md) reaches the requested exposure step
- the live `/portal` route can reach V2 runtime entrypoints without root compatibility links

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
- verify the live bridge or host is explicit and tested
- verify no root-level compatibility symlinks are needed
- verify live AWS writes use one canonical live artifact

## Current cutover posture

Current status: runtime-ready with an internal Shape B deployment bridge mounted, not fully live-state cut over.

V2 `admin.shell_entry` can be reached through the live portal host bridge after the FND/TFF services are running the updated V1 host code.

Trusted-tenant AWS exposure is still blocked on live state mapping. The AWS bridge routes are mounted, but they require explicit configured V2-compatible AWS status input and must not be claimed as live canonical AWS state access until [live_state_authority_and_mapping.md](live_state_authority_and_mapping.md) is implemented.

Future tool work is local slice work, not shared-platform redesign.

The next implementation slice for live cutover is the live AWS profile mapping adapter described in [live_state_authority_and_mapping.md](live_state_authority_and_mapping.md).
