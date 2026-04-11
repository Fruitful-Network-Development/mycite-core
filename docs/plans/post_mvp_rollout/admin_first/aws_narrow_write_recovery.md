# AWS Narrow Write Recovery

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This file records the minimum rollback and manual recovery procedure for `admin_band2.aws_narrow_write_surface`.

## Scope

This recovery guidance applies only to the bounded AWS narrow-write slice that updates `selected_verified_sender`.

It does not authorize:

- direct provider-admin bypass
- secret editing
- broad mailbox provisioning
- manual newsletter send

## Recovery prerequisites

- the last accepted audit record for `aws.operational.write.accepted` is available through the existing local-audit path
- the current AWS status snapshot file is available to internal operators
- the affected tenant scope and profile id are known

## Preferred recovery path

Use the same bounded slice to restore the previous verified sender when the prior known-good sender is still valid.

Checklist:

- confirm the incorrect `selected_verified_sender` through `admin.aws.read_only`
- identify the prior known-good sender from approved operational records
- execute `admin.aws.narrow_write` with the prior known-good sender
- confirm the restored value through the read-after-write result
- confirm the follow-up state again through `admin.aws.read_only`

## Manual recovery path

Use manual recovery only when the prior verified sender cannot be restored through the bounded write slice.

Checklist:

- pause tenant exposure to the write slice if needed
- inspect the latest local-audit records for the affected tenant scope and profile id
- restore `selected_verified_sender` in the AWS status snapshot to the last known-good value
- keep the change limited to the canonical newsletter operational profile and the mirrored top-level selected sender field
- rerun `admin.aws.read_only` to confirm the restored state
- record the manual recovery action in operational notes before re-exposure

## Exposure gate reminder

This file must exist before trusted-tenant exposure of `admin_band2.aws_narrow_write_surface`.
