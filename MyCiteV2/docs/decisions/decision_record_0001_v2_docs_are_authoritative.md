# ADR 0001: V2 Docs Are Authoritative

## Status

Accepted

## Context

V1 drift accumulated through mixed prompts, runtime wrappers, wiki notes, and code-first changes.

## Decision

V2 authority is anchored in this tree:

1. `docs/ontology/structural_invariants.md`
2. `docs/decisions/*.md`
3. `docs/plans/phases/*.md` and `docs/plans/phase_completion_definition.md`
4. `docs/plans/v1-migration/*.md`
5. v1 plan docs
6. v1 code as evidence only

## Consequences

- A prompt or audit note cannot override a v2 ontology file.
- V1 code cannot silently redefine v2 structure.
- Every major root must link back to the authority stack.
