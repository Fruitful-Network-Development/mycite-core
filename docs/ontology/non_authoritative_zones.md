# Non-Authoritative Zones

Authority: [../plans/authority_stack.md](../plans/authority_stack.md)

These surfaces must never become v2 truth.

## Documentation zones

- `docs/wiki/`: secondary notes only
- `docs/audits/`: evidence only
- prompt transcripts and ad hoc agent notes: non-authoritative

## Code and runtime zones

- v1 code under `../mycite_core/`, `../packages/`, and `../instances/`: evidence only
- runtime state outside this repo: deployment artifact only
- utility JSON when datum authority exists: non-authoritative for datum truth
- payload binaries and caches: derived only
- host wrappers and flavor bootstraps: composition only

## Rule

If a non-authoritative zone conflicts with a v2 ontology file, ADR, or phase doc, the non-authoritative zone loses immediately and must be updated or ignored.
