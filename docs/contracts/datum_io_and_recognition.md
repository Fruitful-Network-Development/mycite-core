# Datum IO And Recognition

This document defines the current V2 contract for authoritative datum reads,
read-only recognition, diagnostics, and render hints.

Authority:

- [v2-authority_stack.md](../plans/v2-authority_stack.md)
- [tool_state_and_datum_authority.md](tool_state_and_datum_authority.md)
- `MyCiteV2/packages/ports/datum_store/contracts.py`
- `MyCiteV2/packages/modules/domains/datum_recognition/service.py`

## Source authority

- Authoritative datum reads come from:
  - `data/system/anthology.json`
  - `data/sandbox/<tool>/sources/*.json`
- Supporting sandbox anchor files may be read from `data/sandbox/<tool>/tool*.json`
  only to resolve legal `rf.*` abstraction references for recognition.
- `data/payloads/*.bin`, `data/payloads/cache/*.json`, `data/resources/*`, and
  `data/references/*` remain derived or compatibility surfaces, not canonical
  datum truth.

## Raw preservation

- Raw stored rows are preserved exactly as read.
- Illegal placeholders such as `HERE` remain storable and renderable in the
  authoritative workbench payload.
- Non-sequential datum addresses are preserved; V2 flags irregularity but does
  not renumber or rewrite addresses in this phase.

## Reference legality vs family validity

- `rf.<datum_address>` is a legal anchor-reference form when it parses as an
  anchor datum address.
- Reference-form legality is separate from:
  - whether the supporting anchor row exists
  - whether the anchor resolves to a recognized family
  - whether the stored magnitude matches the family expectation
- Example: `rf.3-1-3` is legal even when the referenced magnitude is `HERE`.
  That case is a content/family diagnostic, not a malformed reference-form
  diagnostic.

## Required diagnostics

Recognition emits zero or more row-level diagnostics chosen from:

- `ok`
- `missing_reference`
- `unresolved_anchor`
- `family_magnitude_mismatch`
- `illegal_magnitude_literal`
- `address_irregularity`
- `unrecognized_family`

## Render hints

Render hints are presentation inputs, not shell truth. They may include:

- expected value kind such as `binary_string`, `numeric_hyphen`, or `literal_text`
- overlay kind for recognized families such as nominal/title babelette,
  SAMRAS-backed ids, or HOPS-backed coordinates
- whether the UI should show raw value by default
- the invariant that overlays/lenses remain presentation-only and do not replace
  raw datum state

The UI may use those hints to show human-readable overlays, but the underlying
payload must continue to expose raw value, recognized family/anchor, and
diagnostic state.
