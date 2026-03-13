# Generic Portal Runtime

Shared runtime image and entrypoint for file-backed MyCite portal instances.

Runtime selection is driven by `PORTAL_RUNTIME_FLAVOR`.
Portal-specific instance content is materialized from per-portal `build.json` specs into the live state root mounted by compose.
