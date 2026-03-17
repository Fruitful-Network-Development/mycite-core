# Development Plan

> **Status: Historical planning snapshot (non-canonical).**
> For current contracts and subsystem boundaries, use `docs/README.md` and the linked canonical docs.

## Active baseline

Active portal specs in this repo:

- `mycite-le_example`
- `mycite-le_fnd`
- `mycite-le_tff`

## Current architectural direction

1. keep the shared runtime generic
2. keep the Data Tool as a core SYSTEM workbench surface
3. keep portal/network/data state file-backed rather than database-backed
4. keep anthology state-owned while contract context is transmitted through MSS compact arrays
5. keep per-portal repo directories moving toward spec-only ownership

## Current implementation priorities

1. stabilize the shared MSS contract context model and its documentation
2. keep anthology mutation and contract recompilation behavior coherent
3. continue network-engine hardening around request logs, contract verification, and foreign datum inheritance
4. keep Data Tool daemon ownership separate from NETWORK MSS resolution
5. remove superseded wrapper language and drift from canonical docs

## Canonical references

- `docs/MSS_COMPACT_ARRAY_SPEC.md`
- `docs/MSS_CONTRACT_CONTEXT_STATUS.md`
- `docs/PORTAL_BUILD_SPEC.md`
- `docs/CANONICAL_DATA_ENGINE.md`
- `docs/NETWORK_PAGE_MODEL.md`
- `docs/DATA_TOOL.md`
