# Module Inventory

This inventory reflects the hard cut that removed the legacy host boundary and made
state-machine ownership explicit.

| Area | Current path(s) | Concern it owns | Target owner |
| --- | --- | --- | --- |
| Runtime entrypoints | `runtime/app.py`, `runtime/bin/run_portal.sh` | Process startup and service launch | `runtime/` |
| Runtime host composition | `mycite_core/runtime_host/*` | Flavor loading, instance context, state roots, runtime paths | `mycite_core/runtime_host` |
| State machine and shell model | `mycite_core/state_machine/*` | Shell controls, actions, reducers, view models, AITAS, workbench document model | `mycite_core/state_machine` |
| MSS and datum resolution | `mycite_core/mss_resolution/*` | Canonical datum compilation, decoding, payload storage, resolution | `mycite_core/mss_resolution` |
| Contracts and line state | `mycite_core/contract_line/*` | Communication-line state, payload registry/history, line context | `mycite_core/contract_line` |
| Tools shared runtime | `tools/_shared/*` | Tool discovery, spec loading, shared runtime helpers | `tools/_shared` |
| Tool-specific behavior | `tools/<tool>/*` | Tool workflows, tool UI, tool state adapters | `tools/<tool>` |
| Instance declarations | `instances/declarations/*` | Portal instance ids, runtime flavors, default state roots | `instances/declarations` |
| Materializers | `instances/materializers/*`, `instances/scripts/*` | Offline state capture/materialization/correction | `instances/materializers` |
| Flavor runtimes | `instances/_shared/runtime/flavors/*/app.py` | App wiring, mounting, enablement, transport | `instances/_shared/runtime/...` |

Immediate result:

- the durable cross-cutting seams now live under `mycite_core/`, `tools/`, `runtime/`, and `instances/`;
- `instances/_shared/...` wrappers still exist where needed, but they delegate to canonical owners instead of defining state meaning;
- the legacy host-boundary package is no longer part of the ownership model.
