# V2 Admin Cutover Readiness

Authority: [../../authority_stack.md](../../authority_stack.md)

This file defines when MyCiteV2 can be treated as the operational admin portal base.

## Cutover statement

MyCiteV2 is the stable admin portal base when:

- `admin.shell_entry` is the intended admin landing path
- shell-owned registry descriptors are the only tool launch surface
- runtime entrypoints are cataloged in `runtime_platform.py`
- Admin Band 0 remains green
- AWS read-only remains green
- AWS narrow-write remains green
- old provider-admin routes are not used as v2 entry surfaces

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

## Current cutover posture

V2 can begin replacing the old admin portal operationally as the stable shell, registry, runtime envelope, AWS read-only, and AWS narrow-write base.

Future tool work is local slice work, not shared-platform redesign.
