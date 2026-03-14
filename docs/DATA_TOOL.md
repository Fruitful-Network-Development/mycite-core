# Data Workbench Contract

## Scope

Applies to:

- `portals/_shared/runtime/flavors/fnd`
- `portals/_shared/runtime/flavors/tff`

SYSTEM hosts the anthology-first Data Tool workbench.

## Canonical runtime

Primary runtime artifacts:

- `data/anthology.json`
- `data/presentation/datum_icons.json`
- `private/daemon_state/data_workspace.json`

Deterministic anthology ordering remains:

- `layer -> value_group -> iteration`

Shared normalization lives in:

- `portals/_shared/portal/data_engine/anthology_normalization.py`

## Workbench behavior

Primary interactions:

- single click: focus summary
- double click: investigate and open `abstraction_path`
- profile editing: update label/pairs/icon for a datum

Canonical data endpoints:

- `GET /portal/api/data/state`
- `POST /portal/api/data/directive`
- `GET /portal/api/data/anthology/table`
- `GET /portal/api/data/anthology/graph`
- `GET /portal/api/data/anthology/profile/<row_id>`
- `POST /portal/api/data/anthology/profile/update`
- `POST /portal/api/data/anthology/append`
- `POST /portal/api/data/anthology/delete`

## MSS contract context role

The Data Tool is the selection and explanation surface for local contract context.

Canonical contract-edit workflow:

1. browse candidate datums from `GET /portal/api/data/anthology/table`
2. inspect a datum and its `abstraction_path` via `GET /portal/api/data/anthology/profile/<row_id>`
3. use those local datum refs as `owner_selected_refs` in `NETWORK > Contracts`
4. compile canonical `owner_mss` from the selected isolated closure

The Data Tool remains anthology-authoritative. Contract compilation lives in the shared MSS layer, not in the Data Tool itself.

## Mutation side effects

Anthology mutation paths that can affect identifier stability or closure now trigger local contract recompilation after compaction and VG0 synchronization.

Current mutation responses include:

- `contract_mss_sync`

This summary reports:

- recompiled local contract ids
- unchanged contract ids
- skipped manual contracts
- failures

## Daemon ownership

Daemon endpoints remain owned by the Data Engine:

- `GET /portal/api/data/daemon/ports`
- `POST /portal/api/data/daemon/resolve`
- `POST /portal/api/data/daemon/resolve_tokens`

These endpoints stay available for Data Tool and tool-package use. NETWORK foreign datum resolution is not daemon-backed; it is contract-MSS-backed.
