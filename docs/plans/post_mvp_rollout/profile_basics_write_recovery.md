# Profile Basics Write Recovery

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

This file records the minimum rollback and manual recovery procedure for `band2.profile_basics_write_surface`.

## Scope

This recovery guidance applies only to the bounded trusted-tenant profile basics write that updates:

- `title`
- `summary`
- `contact_email`
- `public_website_url`

It does not authorize:

- progeny workspace editing
- alias or contract mutation
- media changes
- secret storage
- direct edits to unrelated publication documents

## Recovery prerequisites

- the last accepted audit record for `publication.profile_basics.write.accepted` is available through the trusted-tenant local-audit path
- the affected publication profile id is known
- the current `fnd-<profile_id>.json` tenant profile document is available to internal operators

## Preferred recovery path

Use the same bounded slice to restore the last known-good profile basics values when they are known and still desired.

Checklist:

- confirm the incorrect basics through the current trusted-tenant or operator-visible read surface
- identify the prior known-good values from the accepted local-audit record or a previously reviewed publication artifact
- execute the bounded profile basics write with the prior known-good values
- confirm the restored values through the read-after-write result
- verify the resulting tenant profile document still contains any unrelated preserved fields

## Manual recovery path

Use manual recovery only when the bounded write cannot restore the desired state.

Checklist:

- pause tenant exposure to the write slice if needed
- inspect the latest trusted-tenant local-audit records for the affected tenant scope and profile id
- restore only `title`, `summary`, `contact_email`, and `public_website_url` in the canonical `fnd-<profile_id>.json` tenant profile document
- do not modify unrelated fields or create new publication side documents during recovery
- rerun the bounded read path to confirm the restored values
- record the manual recovery action in operational notes before re-exposure

## Exposure gate reminder

This file must exist before trusted-tenant exposure of `band2.profile_basics_write_surface`.
