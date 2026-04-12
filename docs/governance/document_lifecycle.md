# Document Lifecycle

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This file defines the allowed lifecycle states for documents in `docs/`.

## Allowed states

- `exploratory`: early thinking, scratch notes, or preserved non-authoritative
  notes that may later be promoted.
- `authoritative`: current truth for semantic rules, governance rules, or major
  entrypoint guidance.
- `active-plan`: current unfinished planning that still controls sequencing or
  implementation order.
- `implemented-record`: completed work history, task evidence, and closure
  records.
- `legacy-reference`: retained legacy concept or migration evidence that may
  still be cited, but is not current V2 authority.
- `archived-evidence`: frozen audits, transcripts, historical discussion, or
  evidence packets that should not be reopened as current guidance.
- `delete-candidate`: intentionally quarantined docs that are retained only
  until a later deletion pass.

## Placement rules

- `authoritative` is only valid in `ontology/`, `decisions/`, `contracts/`,
  `testing/`, `glossary/`, governance docs, and root or major README
  entrypoints.
- `active-plan` is only valid in live planning surfaces under `plans/`.
- `implemented-record` is only valid in `records/`.
- `legacy-reference` is only valid in `*/legacy/`,
  `plans/version-migration/`, or explicitly retained evidence links.
- `archived-evidence` is only valid in `audits/`, frozen transcripts, and
  archived personal discussions.
- `exploratory` is valid in `wiki/` and `personal_notes/`.
- `delete-candidate` must never appear in [reading_paths.md](reading_paths.md).

## Promotion and cleanup rules

1. A new shared idea starts in `wiki/` when it is exploratory and meant for
   later promotion.
2. A preserved personal idea, operational note, or discussion starts in
   `personal_notes/`.
3. If a rule becomes current truth, it must move into `ontology/`,
   `decisions/`, `contracts/`, `testing/`, or the active plan surface that
   actually governs it.
4. If work is unfinished and sequenced, it belongs in `plans/`.
5. If work is implemented, the durable completion record belongs in `records/`.
6. If retained V1 or bridge-era material still matters, keep it as
   `legacy-reference` instead of silently treating it as current truth.
7. If a doc exists only to preserve history, keep it as `archived-evidence`.
8. If a doc is no longer needed once unique content is harvested, mark it
   `delete-candidate` in the registry and keep it out of reading paths.

## Registry contract

Every meaningful `.md`, `.yaml`, and `.yml` file under `docs/` must have a row
in [document_registry.yaml](document_registry.yaml) with these fields:

- `path`
- `class`
- `status`
- `owner`
- `canonical_entrypoint`
- `supersedes`
- `superseded_by`
- `last_reviewed`
- `review_cadence`
- `delete_candidate`

Records may also carry:

- `record_id`
- `record_type`
- `sequence_scope`
- `date_completed`
