# Documentation Policy

This repo uses a canonical-docs model to prevent drift.

## Canonical location

- Canonical framework docs live under `docs/`.
- Portal subdirectories should keep docs lightweight and link back to canonical docs.

## Canonical docs

- [`../README.md`](../README.md)
- [`TOOLS_SHELL.md`](TOOLS_SHELL.md)
- [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md)
- [`MSS_COMPACT_ARRAY_SPEC.md`](MSS_COMPACT_ARRAY_SPEC.md)
- [`MSS_CONTRACT_CONTEXT_STATUS.md`](MSS_CONTRACT_CONTEXT_STATUS.md)
- [`REQUEST_LOG_V1.md`](REQUEST_LOG_V1.md)
- [`DATA_TOOL.md`](DATA_TOOL.md)
- [`DATA_TOOL_ICONS.md`](DATA_TOOL_ICONS.md)
- [`repo_policy.md`](repo_policy.md)

## Portal-level docs policy

- Every portal may keep a short `README.md` for run notes and purpose.
- Long-form architecture/spec text belongs in `docs/`.
- Experimental portal notes must identify scope and avoid redefining canonical contracts.

## Reporting policy

- Deployment and operations reports are owned by `srv-infra`.
- `mycite-core` may keep link/pointer docs, not duplicate operational reports.
