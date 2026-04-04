# Module Contracts

This summary maps the canonical module homes after the legacy host-boundary removal.

| Module | Owns | Must not own | Primary dependencies |
| --- | --- | --- | --- |
| `runtime/` | Stable process entrypoints and launch scripts | State meaning, tool business logic, data semantics | `mycite_core/runtime_host`, `instances/declarations` |
| `mycite_core/runtime_host` | Runtime flavor loading, instance context, state-root/path derivation | Shell semantics, tool workflows, route logic | `instances/declarations`, stdlib |
| `mycite_core/state_machine` | Shell actions, controls, reducers, view models, AITAS integration, workbench document shapes | Filesystem topology, tool persistence, host bootstrap | `mycite_core/mss_resolution`, selected shared data-engine helpers |
| `mycite_core/*` domain owners | Contracts, MSS resolution, publication, vault/session, external events, reference exchange | Flavor app transport wiring | other `mycite_core/*` owners as needed |
| `tools/_shared` | Tool catalog, tool spec loading, generic tool runtime helpers | Tool-specific workflows, shell reducer logic | `mycite_core/state_machine`, `mycite_core/runtime_host` |
| `tools/<tool>` | Tool-specific backend/ui/contracts/state adapters | Portal-global path math, unrelated tool logic | `tools/_shared`, stable `mycite_core/*` contracts |
| `instances/declarations` | Named instance declarations and default state roots | Runtime route behavior, shell semantics | `mycite_core/runtime_host` |
| `instances/materializers` | Offline capture/materialize/corrective state utilities | Live request handling, shell behavior | `instances/declarations`, `mycite_core/runtime_host` |
| `instances/_shared/runtime/...` | Flavor app wiring, route mounting, enablement, transport | Canonical state meaning, reducers, path policy | `mycite_core/*`, `tools/*` |

Dependency rule map:

1. `runtime/` may depend on `mycite_core/runtime_host`; it must not own shell or data semantics.
2. `mycite_core/runtime_host` must stay host/runtime focused; it must not absorb reducer or UI meaning.
3. `mycite_core/state_machine` is the canonical shell/state owner; routes and flavor apps should read from it, not recreate it.
4. `tools/_shared` may depend on `mycite_core/state_machine` and `mycite_core/runtime_host`; it must not depend on flavor app modules.
5. `tools/<tool>` may depend on `tools/_shared` and stable `mycite_core/*` contracts; they must not reach into other tools without an explicit shared contract.
6. `instances/declarations` and `instances/materializers` stay offline and state-oriented; they must not acquire live request routing.
7. Flavor app modules remain wiring shells; new cross-cutting logic should not be added there if a canonical `mycite_core` owner already exists.
