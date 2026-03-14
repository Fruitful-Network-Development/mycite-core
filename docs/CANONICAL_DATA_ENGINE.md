# Canonical Data Engine

## Canonical source

Portal data runtime is file-backed.

Canonical data artifacts:

- `data/anthology.json`
- `data/presentation/datum_icons.json`
- request logs and hosted/network metadata under `private/network/**`

Repo `build.json` files may seed contract/network data, but anthology content remains state-owned and is not overwritten by materialization.

## Datum and mediation model

Canonical datum ordering remains:

1. layer
2. value group
3. iteration

Shared helpers:

- anthology normalization: `portals/_shared/portal/data_engine/anthology_normalization.py`
- mediation registry: `portals/_shared/portal/mediation/registry.py`
- MSS contract context: `docs/MSS_COMPACT_ARRAY_SPEC.md`

## Reference model

Canonical network-facing datum refs:

- `<msn_id>.<datum>`

Compatibility policy:

- local refs remain readable
- legacy hyphen-qualified refs remain readable
- new network-facing writes use dot-qualified refs

## Daemon ownership

Daemon resolution remains owned by the Data Engine.

Canonical Data Engine daemon routes:

- `GET /portal/api/data/daemon/ports`
- `POST /portal/api/data/daemon/resolve`
- `POST /portal/api/data/daemon/resolve_tokens`

These routes are retained for Data Tool and tool-package usage. NETWORK foreign datum resolution does not use a separate daemon wrapper; it resolves through contract MSS context.

## MSS contract sync boundary

The Data Engine is responsible for keeping anthology-derived contract context coherent after anthology mutations.

Current rule:

- after anthology compaction and VG0 synchronization, recompile `owner_mss` for local contracts with non-empty `owner_selected_refs`
- do not rewrite manual `owner_mss` values when no `owner_selected_refs` are stored

Current mutation surfaces covered:

- anthology append
- anthology delete
- anthology profile update
- time-series mutations that write anthology rows

## Storage boundary

There is no portal application database in this runtime. Portal data, hosted metadata, request logs, progeny profiles, vault state, and workbench state remain JSON/ndjson/file backed.
