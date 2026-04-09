# AWS-First Surface

Authority: [../../authority_stack.md](../../authority_stack.md)

This file defines the first real tool-bearing target in the admin-first path.

## Why AWS is first

AWS is first because it is the narrowest high-value admin surface with strong existing evidence and explicit v1 correction rules.

It has all of the following:

- concrete existing operational pressure
- explicit v1 drift notes in `tool_dev.md`
- a clear retirement rule for standalone `newsletter-admin`
- a natural read-only first slice
- a bounded write candidate that can follow later

Maps and AGRO-ERP depend on broader mediation surfaces and are therefore not the fastest safe operational replacement path.

## First AWS slice

The first AWS slice is:

`admin_band1.aws_read_only_surface`

It is a read-only AWS operational visibility surface launched through the admin shell and tool registry.

## What that first AWS slice must show

- mailbox or profile readiness state
- SMTP-ready, Gmail-pending, and verified evidence state
- selected verified sender
- canonical newsletter operational profile summary
- compatibility warning surface when progeny newsletter metadata disagrees with canonical newsletter profile JSON
- inbound-capture and dispatch-health summary where safe to expose

## What that first AWS slice must not do

- no provisioning writes
- no manual newsletter send
- no Gmail-verified state override without evidence
- no PayPal or analytics controls
- no secret display
- no direct provider dashboard bypassing the admin shell

## Prerequisites before AWS can be exposed

- `Admin Band 0` shell entry is stable
- the tenant-safe runtime envelope is stable
- the admin home/status surface is stable
- the tool registry/launcher surface is stable and deny-by-default
- the AWS slice has a registry entry, a runtime entrypoint plan, and a gate record
- the standalone `newsletter-admin` surface is absent from the registry

## Likely later seams

This file does not authorize new ports or adapters yet.

It does identify the likely future seam shapes:

- one AWS read-only status seam
- one AWS narrow write seam
- optional use of existing `local_audit` for accepted write-path audit emission

The exact port and adapter names remain frozen until the AWS read-only slice is approved for build.

## First AWS narrow write candidate

The first AWS narrow write candidate is:

`admin_band2.aws_narrow_write_surface`

Its job is limited to bounded AWS operational profile stewardship, such as:

- selecting the active verified sender
- updating the canonical newsletter operational profile fields that AWS owns operationally

It must not include:

- manual newsletter send
- raw credential editing
- broad mailbox provisioning
- cross-provider admin writes
