# Governance

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This directory governs the `docs/` system itself: lifecycle, registry, reading
paths, and cleanup posture.

- It does not replace semantic precedence. If governance guidance conflicts with
  ontology, ADRs, contracts, or active plans, the higher-precedence source in
  [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md) wins.
- Use [document_lifecycle.md](document_lifecycle.md) for allowed document
  states and placement rules.
- Use [document_registry.yaml](document_registry.yaml) as the control plane for
  ownership, lifecycle, canonical entrypoints, and supersession.
- Use [reading_paths.md](reading_paths.md) for task-based navigation through the
  current docs tree.
- Use [../personal_notes/README.md](../personal_notes/README.md) for preserved
  non-authoritative notes that should not be folded back into shared authority.
