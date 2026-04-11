# Admin Runtime Envelope

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This file defines the tenant-safe runtime envelope that every admin-first slice must pass through.

## Purpose

The admin runtime envelope makes admin rollout safe by constraining what the runtime may compose and what it may return.

The envelope exists before tool exposure so future tools inherit the same safety boundary.

## Envelope responsibilities

- receive tenant-scoped admin requests
- normalize the requested admin slice id
- deny access to slices that are not listed in the registry/launcher
- compose only approved runtime entrypoints
- attach rollout band and exposure posture to the response
- redact secrets, instance paths, and provider-internal details
- keep runtime behavior composition-only

## Minimum envelope fields

Every future admin runtime response must carry:

- `schema`
- `admin_band`
- `exposure_status`
- `tenant_scope`
- `requested_slice_id`
- `slice_id`
- `entrypoint_id`
- `read_write_posture`
- `shell_state`
- `surface_payload`
- `warnings`
- `error`

These are runtime-envelope fields, not tool-owned semantics.

The code-level helper is `instances/_shared/runtime/runtime_platform.py`.

## Tenant-safe rules

- The runtime envelope may never expose filesystem roots, instance ids, raw utility paths, or provider secret values.
- Trusted-tenant admin exposure must be deny-by-default.
- A tool slice may become trusted-tenant visible only when:
  - its slice file exists
  - its runtime entrypoint is cataloged
  - its exposure status is approved
  - its output surface is explicitly redacted and tested

## Forbidden drift

- no tool imports deciding who may launch that tool
- no direct provider route mounted beside the envelope
- no host-owned fallback behavior when a slice is missing
- no flavor-specific runtime branches in the admin-first band
- no secret-bearing exception payloads

## Tests required before trusted-tenant admin use

- integration test for allow and deny paths through the envelope
- architecture boundary test proving the runtime imports only approved inward layers
- negative test proving unapproved slices cannot be launched
- response-shape test proving tenant-safe redaction behavior
