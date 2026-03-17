# Documentation Policy

This repo uses a canonical-docs model to prevent drift.

## Canonical location

- Canonical framework docs live under `docs/`.
- Portal subdirectories should keep docs lightweight and link back to canonical docs.
- `docs/README.md` is the maintained documentation map and classification index.

## Canonical docs

- [`README.md`](README.md)
- [`MSS_COMPACT_ARRAY_SPEC.md`](MSS_COMPACT_ARRAY_SPEC.md)
- [`MSS_CONTRACT_CONTEXT_STATUS.md`](MSS_CONTRACT_CONTEXT_STATUS.md)
- [`CANONICAL_DATA_ENGINE.md`](CANONICAL_DATA_ENGINE.md)
- [`NETWORK_PAGE_MODEL.md`](NETWORK_PAGE_MODEL.md)
- [`PORTAL_CORE_ARCHITECTURE.md`](PORTAL_CORE_ARCHITECTURE.md)
- [`PORTAL_BUILD_SPEC.md`](PORTAL_BUILD_SPEC.md)
- [`DATA_TOOL.md`](DATA_TOOL.md)
- [`SANDBOX_ENGINE.md`](SANDBOX_ENGINE.md)
- [`AGRO_ERP_TOOL.md`](AGRO_ERP_TOOL.md)

## Portal-level docs policy

- Every portal may keep a short `README.md` for run notes and purpose.
- Long-form architecture/spec text belongs in `docs/`.
- Experimental portal notes must identify scope and avoid redefining canonical contracts.

## Classification policy

- Docs should be explicitly treated as `canonical`, `supporting`, `background`, or `historical`.
- Report/progress documents are not canonical unless explicitly promoted.
- Historical material should be retained only when it explains current behavior lineage.
- Background notes may remain, but must not redefine runtime contracts.

## Reporting policy

- Deployment and operations reports are owned by `srv-infra`.
- `mycite-core` may keep link/pointer docs, not duplicate operational reports.
