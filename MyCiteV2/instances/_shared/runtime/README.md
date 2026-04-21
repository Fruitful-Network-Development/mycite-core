# Runtime

Authority: [../../../../docs/contracts/portal_shell_contract.md](../../../../docs/contracts/portal_shell_contract.md)

`instances/_shared/runtime/` owns shared runtime composition only.

Implemented in shared runtime:

- one shared portal runtime descriptor catalog and envelope helper
- one shell entrypoint for SYSTEM, NETWORK, and UTILITIES root surfaces
- one SQL-backed SYSTEM datum-file workbench rooted in the system sandbox anchor file for migrated authority surfaces
- one NETWORK read-only system-log workbench rooted in `data/system/system_log.json`
- one shell entrypoint family for SYSTEM child surfaces
- one tool runtime family for SYSTEM tool work pages
- one read-only SQL-backed `workbench_ui` tool runtime for two-pane spreadsheet-like document/version and row inspection
- one utility surface family for tool exposure and integration state
- one SQL-backed local-audit composition path for normalized portal-shell requests on migrated SYSTEM surfaces

Shared runtime authority rules:

- migrated `SYSTEM` surfaces require `authority_db_file`
- missing or uninitialized SQL authority is a readiness failure, not a silent filesystem bootstrap
- filesystem datum/audit adapters are no longer active shared-runtime authority for migrated SYSTEM surfaces
- directive overlays remain additive only and must never mutate authoritative datum rows
- shared directive overlays are imported only from explicit manifests; absent a manifest, directive SQL tables may remain empty

Not implemented in shared runtime:

- flavor-specific runtime composition
- sandboxes
- broad datum mutation or repair flows
