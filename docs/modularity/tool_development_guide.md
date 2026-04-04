# Tool Development Guide

Future tools should be added without recreating portal-history drift.

## Required shape

Each standalone tool belongs under `tools/<tool_name>/` and should use this
internal shape:

- `backend/`
- `ui/`
- `contracts/`
- `state_adapter/`
- `migrations/` when the tool persists evolving state

## State rules

1. Tool state is always instance-scoped.
2. Tool state roots resolve from the instance `private/` directory through a
   state-adapter module, not through ad hoc `Path(...)` math inside routes.
3. Canonical live state belongs under:
   `/srv/mycite-state/instances/<instance_id>/private/utilities/tools/<tool-namespace>/...`
4. Do not write tool state into the repo.
5. Do not treat `/srv/compose/portals/state/*` as equal-truth state; those
   paths are compatibility seams only.

## Dependency rules

1. Tool backends may depend on:
   `tools/_shared`, `mycite_core/state_machine`, `mycite_core/runtime_host`, and
   other explicit stable contracts.
2. Tool backends must not import flavor app modules directly.
3. Tool UIs must not reach around their state adapters to compute filesystem
   paths.
4. Tool-specific business rules belong in the tool module, not in
   `portals/_shared/portal/application/service_tools.py`.

## Registration rules

1. Add or update the service-tool catalog entry in
   `tools/_shared/tool_contracts/service_catalog.py` only if the tool needs the
   service-tool mediation surface.
2. Keep tool capability metadata aligned with `mycite_core/state_machine`.
3. Prefer thin legacy registration shims over duplicated tool implementations.

## Compatibility rules

1. If a tool needs a temporary compatibility surface, name it explicitly
   `compat` or `webhook_compat`.
2. Compatibility code must not become the primary backend.
3. Document every compatibility seam in
   `docs/modularity/compatibility_seams.md`.

## Minimum checks for a new tool

Before considering a tool integration complete:

1. add a state adapter that resolves the instance-scoped root;
2. add or update tests covering state-root resolution;
3. verify the tool can be discovered through the shared tool runtime if
   applicable;
4. verify the tool does not import flavor-specific app modules for shared
   behaviors;
5. update `docs/modularity/module_map.json` if the dependency surface changed.
