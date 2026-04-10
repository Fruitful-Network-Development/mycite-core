# Runtime Alignment Report

## Current alignment

- `runtime/app.py` owns the stable process entrypoint.
- `mycite_core/runtime_host/*` owns runtime flavor loading, instance-context creation, and canonical path/state-root derivation.
- `mycite_core/state_machine/*` owns shell controls, actions, reducers, view-model derivation, AITAS integration, and workbench document contracts.
- `tools/_shared/*` owns shared tool runtime/spec/catalog logic.
- `instances/declarations/registry.py` owns active instance declarations.
- `instances/_shared/runtime/flavors/*/app.py` owns flavor wiring only.

## Transitional wrappers still tolerated

- `instances/_shared/portal/runtime_paths.py`
- `instances/_shared/portal/application/runtime/instance_context.py`
- `instances/_shared/portal/application/shell/contracts.py`
- `instances/_shared/portal/application/shell/tools.py`
- `instances/_shared/portal/application/shell/runtime.py`
- `instances/_shared/portal/data_engine/aitas_context.py`

These files now delegate directly to `mycite_core` owners and must not regain business logic.

## State and materializer alignment

- `instances/declarations/registry.py` provides default instance ids, runtime flavors, and canonical state roots.
- `instances/scripts/portal_build.py` consumes those declarations instead of maintaining a second portal map.
- `instances/scripts/correct_portal_sandbox_contract.py` resolves default state roots through `mycite_core.runtime_host.state_roots`.

## Validation posture

Compile checks and targeted unit tests should validate:

- `mycite_core/runtime_host/*`
- `mycite_core/state_machine/*`
- shell route wiring
- MSS and contract-context flows
- runtime loader behavior
