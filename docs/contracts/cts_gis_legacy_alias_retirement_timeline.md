# CTS-GIS Legacy Alias Retirement Timeline

This document defines retirement timing for legacy CTS-GIS request aliases and compatibility fields.

## Scope

Legacy aliases covered:

- `mediation_state.attention_node_id`
- `mediation_state.intention_token`
- top-level `selected_row_address`
- top-level `selected_feature_id`
- legacy tool/document identifiers that map to prior `maps` naming

## Timeline

### Phase 1: Deprecation Active (current)

- Runtime keeps compatibility parsing for body aliases listed above.
- Runtime returns canonical `tool_state` in responses.
- Runtime emits compatibility notes in contract docs.
- Legacy `maps` tool/document identifiers remain hard-rejected.

### Phase 2: Warning Escalation

- Compatibility aliases continue to parse for audit scenarios only.
- Production strict flows should not rely on alias parsing.
- CI and contract tests fail when new code introduces alias-first examples.
- Documentation examples are canonical-only (`tool_state` + `runtime_mode`).

### Phase 3: Retirement

- Alias parsing is removed from default CTS-GIS runtime paths.
- `tool_state` canonical keys become mandatory for CTS-GIS state transfer.
- Audit-mode compatibility adapters (if retained) are explicitly versioned and isolated.

## Exit Criteria

Alias retirement may proceed when all are true:

- strict-mode fixtures use canonical `tool_state` only
- no active client renderer emits alias payloads
- migration communication is complete for operator scripts
- contract tests assert absence of alias guidance outside historical notes

## Operational Notes

- Keep legacy compatibility only where it prevents breaking historical replay workflows.
- Do not reintroduce deprecated identifiers in new docs, test fixtures, or UI action adapters.
- Any future compatibility extension must include explicit sunset criteria and timeline updates here.
