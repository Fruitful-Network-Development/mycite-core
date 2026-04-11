# Admin Home And Status Surface

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This file defines the default surface shown by the admin shell entry.

## Purpose

The admin home/status surface is the operator orientation layer.

It answers:

- where am I
- which admin band is active
- what is intentionally available
- what is still internal-only
- whether the admin runtime is stable enough to proceed

## Required contents

- current admin band
- current exposure posture
- current tenant scope
- approved admin slices and tools
- explicit read-only or writable posture
- runtime health summary for the shared admin path
- audit-path or local operational health summary where available

## Must not contain

- hidden provider actions
- direct tool launch side effects
- provider-specific deep controls
- instance paths
- secret-bearing fields
- raw compatibility warnings that belong inside a specific tool slice

## Why this comes before AWS

AWS is the first real tool-bearing target, but it should not be the first operator landing surface.

The admin home/status surface has to exist first so:

- trusted users know which slices are intentional
- AWS does not become the accidental shell
- later tools do not each invent their own landing page

## Exit criteria before AWS begins

- the admin shell entry is stable
- the admin home/status surface is the default landing payload
- the tool registry/launcher is defined, even if its first entries are internal-only
- the surface clearly marks AWS as not yet approved until the AWS slice passes its gate
