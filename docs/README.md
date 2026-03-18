# mycite-core Documentation Map

This index is the canonical navigation point for repository docs under `docs/`.

## Classification labels

- **Canonical**: implementation contract for active runtime behavior.
- **Supporting**: current implementation detail or reference that extends canonical docs.
- **Background**: useful design context; not authoritative runtime contract.
- **Historical**: preserved snapshot/report for past phases; not authoritative for current behavior.

## Canonical docs (active contracts)

- `MSS_COMPACT_ARRAY_SPEC.md`
- `MSS_CONTRACT_CONTEXT_STATUS.md`
- `CANONICAL_DATA_ENGINE.md`
- `NETWORK_PAGE_MODEL.md`
- `PORTAL_CORE_ARCHITECTURE.md`
- `PORTAL_BUILD_SPEC.md`
- `DATA_TOOL.md`
- `SANDBOX_ENGINE.md`
- `ANTHOLOGY_BASE_OVERLAY.md`
- `AGRO_ERP_TOOL.md`
- `RESOURCE_STORAGE_CONVENTIONS.md`
- `PORTAL_UNIFIED_MODEL.md`

## Supporting docs (current, non-authoritative)

- `CONTRACT_COMPACT_INDEX.md`
- `CONTRACT_UPDATE_PROTOCOL.md`
- `AITAS_CONTEXT_MODEL.md`
- `EXTERNAL_RESOURCE_ISOLATES.md`
- `INHERITED_RESOURCE_CONTRACT_MODULE.md`
- `DATA_TOOL_ICONS.md`
- `TOOLS_SHELL.md`
- `REQUEST_LOG_V1.md`
- `SHELL_COMPOSITION.md`
- `SYSTEM_WORKBENCH_ARCHITECTURE.md`
- `ANTHOLOGY_WORKBENCH_ARCHITECTURE.md`
- `PORTAL_SHELL_UI.md`
- `HOSTED_SESSIONS.md`
- `HOSTED_SHELL_ALIAS.md`
- `PROGENY_CONFIG_MODEL.md`
- `PROGENY_PROFILE_CARDS.md`
- `AWS_EMAILER_ABSTRACTION.md`
- `PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md`
- `TIME_SERIES_ABSTRACTION.md`
- `SAMRAS_PAGE.md`
- `ANTHOLOGY_GRAPH_EXTRACTION_MODEL.md`
- `DATUM_MEDIATION_DEFAULTS.md`
- `POC_WORKSPACE_MODEL.md`
- `COMPOSE_FILE_TREE.md`

## Background docs (non-canonical by design)

- `mss_notes.md`

## Historical reports (demoted from canonical use)

- `MYCITE_CORE_DEVELOPMENT_REPORT.md`
- `AGRO_ERP_PROGRESS.md`
- `AGRO_ERP_MVP_CONTRACT.md`
- `AGRO_ERP_MVP_VALIDATION_REPORT.md`
- `AGRO_ERP_MSS_OPEN_RESOURCE_REPORT.md`
- `DEVELOPMENT_PLAN.md`

## Policy and repository docs

- `DOCUMENTATION_POLICY.md`
- `repo_policy.md`

## Cross-links by subsystem

- **MSS + contracts**: `MSS_COMPACT_ARRAY_SPEC.md`, `MSS_CONTRACT_CONTEXT_STATUS.md`, `CONTRACT_COMPACT_INDEX.md`, `CONTRACT_UPDATE_PROTOCOL.md`, `NETWORK_PAGE_MODEL.md`
- **Data engine + Data Tool**: `CANONICAL_DATA_ENGINE.md`, `DATA_TOOL.md`, `ANTHOLOGY_BASE_OVERLAY.md`, `DATA_TOOL_ICONS.md`, `ANTHOLOGY_WORKBENCH_ARCHITECTURE.md`
- **Sandbox + inherited TXA path**: `SANDBOX_ENGINE.md`, `AGRO_ERP_TOOL.md`, `CANONICAL_DATA_ENGINE.md`
- **AGRO ERP**: `AGRO_ERP_TOOL.md`, `AGRO_ERP_INTENTION.md`, `SANDBOX_ENGINE.md`
- **Shell/runtime/build**: `PORTAL_CORE_ARCHITECTURE.md`, `TOOLS_SHELL.md`, `PORTAL_BUILD_SPEC.md`, `SHELL_COMPOSITION.md`
- **Compose/runtime deployment layout**: `COMPOSE_FILE_TREE.md`, `PORTAL_BUILD_SPEC.md`, `../README.md`
