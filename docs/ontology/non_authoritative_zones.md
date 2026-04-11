# Non-Authoritative Zones

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

These surfaces must never become v2 truth.

## Documentation zones

- `docs/wiki/`: secondary notes only
- `docs/audits/`: evidence only
- `docs/records/`: completion evidence, not higher architecture authority
- `docs/plans/legacy/`, `docs/contracts/legacy/`, and `docs/wiki/legacy/`: legacy evidence only
- prompt transcripts and ad hoc agent notes: non-authoritative

## Code and runtime zones

- `MyCiteV1/`: implementation-history evidence and retirement-review scope only
- runtime state outside this repo: deployment artifact only
- copied snapshots, bridge-only shims, and compatibility links: never higher authority than repo docs and repo-owned code
- utility JSON when datum authority exists: non-authoritative for datum truth
- payload binaries and caches: derived only
- host wrappers and flavor bootstraps: composition only

## Rule

If a non-authoritative zone conflicts with a v2 ontology file, ADR, or phase doc, the non-authoritative zone loses immediately and must be updated or ignored.
