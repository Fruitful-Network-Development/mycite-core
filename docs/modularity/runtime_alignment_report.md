# Runtime Alignment Report

## Scope

This pass was an offline engineering-structure refactor inside `mycite-core`.
It did not restart or replace the live native services. The objective was to
re-home stable cross-cutting logic into canonical capability modules while
keeping the current runtime entrypoints valid.

## Canonicalized entrypoints and shared modules

- `runtime/app.py` now owns flavor loading.
- `runtime/bin/run_portal.sh` now owns the canonical Gunicorn launch contract.
- `portal_core/composition/runtime_loader.py` owns runtime flavor import logic.
- `portal_core/composition/instance_context.py` owns instance-context creation.
- `portal_core/shared/runtime_paths.py` and
  `portal_core/shared/state_roots.py` own canonical path and state-root
  derivation.
- `portal_core/shell/*` owns shell verbs and tool-capability normalization.
- `tools/_shared/*` owns shared tool runtime/spec/catalog logic.
- `instances/declarations/registry.py` owns active instance declarations.

## Transitional wrappers retained

- `portals/runtime/app.py`
- `portals/runtime/bin/run_portal.sh`
- `portals/_shared/portal/runtime_paths.py`
- `portals/_shared/portal/application/runtime/instance_context.py`
- `portals/_shared/portal/application/shell/contracts.py`
- `portals/_shared/portal/application/shell/tools.py`
- `portals/_shared/portal/tools/runtime.py`
- `portals/_shared/portal/tools/specs.py`

These wrappers remain because the current native runtime and several tests still
load through the legacy paths.

## State and materializer alignment

- `instances/declarations/registry.py` now provides default instance ids,
  runtime flavors, and canonical state roots.
- `portals/scripts/portal_build.py` now consumes those declarations instead of
  hardcoding a second copy of the active portal map.
- `portals/scripts/correct_portal_sandbox_contract.py` now resolves its default
  state root through `portal_core.shared.state_roots.canonical_instances_root()`.
- FND admin integrations now resolve canonical AWS and PayPal tool state roots
  through dedicated tool state-adapter modules.

## Validation performed

### Compile validation

Command:

```bash
python3 -m py_compile \
  runtime/app.py \
  portal_core/shared/state_roots.py \
  portal_core/shared/runtime_paths.py \
  portal_core/composition/runtime_loader.py \
  portal_core/composition/instance_context.py \
  portal_core/shell/contracts.py \
  portal_core/shell/tool_capabilities.py \
  instances/declarations/registry.py \
  tools/_shared/tool_contracts/service_catalog.py \
  tools/_shared/tool_contracts/specs.py \
  tools/_shared/tool_state_api/paths.py \
  tools/_shared/tool_state_api/runtime.py \
  tools/analytics/state_adapter/paths.py \
  tools/aws_csm/state_adapter/paths.py \
  tools/aws_csm/state_adapter/profile.py \
  tools/paypal_csm/state_adapter/paths.py \
  tools/keycloak_sso/state_adapter/paths.py \
  tools/operations/state_adapter/paths.py \
  portals/runtime/app.py \
  portals/_shared/portal/runtime_paths.py \
  portals/_shared/portal/application/runtime/instance_context.py \
  portals/_shared/portal/application/shell/contracts.py \
  portals/_shared/portal/application/shell/tools.py \
  portals/_shared/portal/tools/runtime.py \
  portals/_shared/portal/tools/specs.py \
  portals/_shared/portal/application/service_tools.py \
  portals/scripts/portal_build.py \
  portals/scripts/correct_portal_sandbox_contract.py \
  portals/_shared/runtime/flavors/fnd/portal/api/admin_integrations.py
```

Result: passed.

### Regression tests covering existing runtime-facing seams

Command:

```bash
./.venv/bin/python -m pytest \
  tests/test_runtime_paths.py \
  tests/test_tool_runtime.py \
  tests/test_portal_build_spec.py \
  tests/test_admin_integrations_aws_csm.py \
  tests/test_service_tool_mediation.py
```

Result: `27 passed`.

### Boundary and loader tests added in this pass

Command:

```bash
./.venv/bin/python -m pytest \
  tests/test_module_boundaries.py \
  tests/test_runtime_loader.py
```

Result: `7 passed`.

### Canonical boundary validation script

Command:

```bash
./runtime/bin/validate_modular_boundaries.sh
```

Result: `22 passed`.

## Runtime conclusion

The current runtime entrypoints still work as compatibility surfaces, but the
engineering source of truth for the extracted concerns now lives in the new
canonical modules. No live-service restart was required to validate this pass.
