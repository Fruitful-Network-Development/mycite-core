# Module Contracts

This summary maps the canonical module homes introduced or reinforced in this
pass. Detailed contract docs live under `docs/modularity/contracts/`.

| Module | Owns | Must not own | Primary dependencies |
| --- | --- | --- | --- |
| `runtime/` | Stable process entrypoints, launch scripts, boundary validation | Portal behavior, tool state, data semantics | `portal_core/composition` |
| `portal_core/composition` | Instance loading, runtime flavor loading, instance context | Tool business logic, Flask routes, state mutation | `portal_core/shared`, `instances/declarations` |
| `portal_core/shared` | Runtime path helpers, canonical state-root helpers | Tool-specific behavior, shell semantics | None or stdlib only |
| `portal_core/shell` | Shell verbs, inspector contracts, tool capability rules | Tool state persistence, data-engine mutation | `portal_core/shared` |
| `tools/_shared` | Tool catalog, tool spec loading, tool runtime helpers | Tool-specific workflows, shell verbs, instance declarations | `portal_core/shell`, `portal_core/shared` |
| `tools/<tool>` | Tool-specific backend/ui/contracts/state adapters | Portal-global path math, unrelated tool logic | `tools/_shared`, `portal_core/*` via stable interfaces |
| `instances/declarations` | Named instance declarations and default state roots | Runtime route behavior, tool state mutation | `portal_core/shared` |
| `instances/materializers` | Offline capture/materialize/corrective state utilities | Live request handling, shell behavior | `instances/declarations`, `portal_core/shared` |

Detailed contract docs:

- [composition.md](./contracts/composition.md)
- [state_machine.md](./contracts/state_machine.md)
- [data_engine.md](./contracts/data_engine.md)
- [contracts.md](./contracts/contracts.md)
- [sandboxes.md](./contracts/sandboxes.md)
- [vault.md](./contracts/vault.md)
- [profiles.md](./contracts/profiles.md)
- [shell.md](./contracts/shell.md)
- [tools_shared.md](./contracts/tools_shared.md)
- [analytics.md](./contracts/analytics.md)
- [aws_csm.md](./contracts/aws_csm.md)
- [paypal_csm.md](./contracts/paypal_csm.md)
- [keycloak_sso.md](./contracts/keycloak_sso.md)
- [operations.md](./contracts/operations.md)

Dependency rule map:

1. `runtime/` may depend on `portal_core/composition`; it must not depend on
   tool-specific state adapters directly.
2. `portal_core/shared` must stay low-level and path-focused; it must not import
   flavor apps or tool business logic.
3. `portal_core/shell` may depend on `portal_core/shared`; tool modules may
   depend on shell contracts, but shell must not depend on tool-specific state.
4. `tools/_shared` may depend on `portal_core/shell` and `portal_core/shared`;
   it must not depend on flavor app modules.
5. `tools/<tool>` may depend on `tools/_shared` and stable `portal_core/*`
   contracts; it must not reach into other tool modules without an explicit
   shared contract.
6. `instances/declarations` and `instances/materializers` must stay offline and
   state-oriented; they must not acquire live request routing.
7. Flavor app modules remain temporary composition shells; new cross-cutting
   logic should not be added there if a canonical module home already exists.

