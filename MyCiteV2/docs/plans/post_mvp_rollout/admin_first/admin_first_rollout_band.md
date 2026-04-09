# Admin-First Rollout Band

Authority: [../../authority_stack.md](../../authority_stack.md)

This file defines the admin-first rollout ordering that replaces the old portal operationally without widening general client rollout.

## First stable admin operating band

The first stable admin operating band is:

`Admin Band 0 Internal Admin Replacement`

This band is nested under the global `Band 0 Internal Only` posture.

Its purpose is to create the minimum stable admin operating system needed before any tool-bearing surface becomes trusted-tenant visible.

## Admin-first band stack

| Admin-first band | Audience | Required slices | Allowed exposure | Exit criteria |
|---|---|---|---|---|
| `Admin Band 0 Internal Admin Replacement` | internal operators and builders only | admin shell entry, tenant-safe runtime envelope, admin home/status, tool registry/launcher | internal-only | all four slices are stable, tool registry is deny-by-default, and AWS read-only slice is specified clearly |
| `Admin Band 1 Trusted-Tenant AWS Read-Only` | trusted tenant admins and internal operators | the `Admin Band 0` slices plus one AWS read-only slice | trusted-tenant read-only | AWS read-only slice passes its gate and proves the first tool-bearing path without hidden writes |
| `Admin Band 2 Trusted-Tenant AWS Narrow Write` | trusted tenant admins only | the `Admin Band 1` stack plus one bounded AWS write slice | trusted-tenant narrow write | AWS narrow write proves auditability, rollback clarity, and read-after-write behavior |

## Required operating order

The admin-first planning and implementation order is fixed:

1. one stable admin shell entry
2. one tenant-safe admin runtime envelope
3. one admin home/status surface
4. one tool registry/launcher surface
5. one AWS-first read-only surface
6. one AWS-first narrow writable/admin workflow if justified
7. Maps follow-on planning and then implementation
8. AGRO-ERP follow-on planning and then implementation

Maps may not displace AWS.
AGRO-ERP may not displace Maps.

## What must exist before the old portal can begin to be operationally replaced

All of the following must be true:

- the admin shell entry is the only stable shell landing surface
- the runtime envelope is tenant-safe and composition-only
- the admin home/status surface tells an operator which slices are intentionally available
- the tool registry/launcher catalogs launchable slices without scanning tool packages dynamically
- direct provider-admin routes are treated as legacy evidence, not as v2 replacement structure

## What must be true before any admin tool becomes trusted-tenant usable

All of the following must be true:

- `Admin Band 0` is stable
- the tool registry/launcher exists and is deny-by-default
- the admin shell still owns discoverability and launch legality
- the tool-bearing slice has its own slice file and gate record
- the tool-bearing runtime entrypoint is cataloged in `runtime_entrypoints.md`
- no direct tool route bypasses the admin shell entry
- no secret-bearing or provider-internal fields leak in the trusted-tenant response

## Forbidden drift during the admin-first track

- no direct reconstruction of `fnd/app.py` style host-owned service navigation
- no tool-owned shell verbs or tool-owned launch legality
- no provider-admin bundle that mixes AWS, PayPal, analytics, and newsletter into one slice
- no standalone `newsletter-admin` comeback
- no Maps or AGRO work before the AWS-first path is proven
- no flavor-specific runtime copies
