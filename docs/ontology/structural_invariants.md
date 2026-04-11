# Structural Invariants

This file is the highest-precedence structural source in v2. See [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md).

## Non-negotiable truths

1. Domain logic must not depend on adapters, tools, hosts, or runtime wrappers.
2. Navigation state must be pure, explicit, and serializable.
3. `mediation_surface` is state-machine surface behavior, not a core utility bucket.
4. Tools attach through shell-defined surfaces. Tools do not invent their own shell model.
5. Datum authority must be explicit and fail-closed.
6. Utility JSON is not datum truth when a datum authority exists.
7. Payload binaries and caches are derived artifacts, never source truth.
8. Sandboxes orchestrate staging and mediation boundaries. They do not own domain semantics.
9. Hosts compose modules. Hosts do not own domain logic.
10. No module may import outward across dependency layers.
11. V2 documentation in this tree is authoritative for v2. Prompt history is not.
12. V1 code is evidence only and must never be copied as a structural template.

## Immediate consequences

- No `packages/modules/services/` bucket exists in v2.
- No `packages/core/mediation/` bucket exists in v2.
- No `vault_session/` v2 root exists. That v1 concern is split deliberately.
- No instance-led placeholder tree such as `instances/FND` exists in this scaffold.
