# Data Workbench Contract

## Scope

Applies to:

- `portals/_shared/runtime/flavors/fnd`
- `portals/_shared/runtime/flavors/tff`

`SYSTEM` hosts the unified Data Tool workbench.

The current contract is one layered `SYSTEM` workbench with:

- a left **control panel**
- a center anthology-style table surface
- a right **Details** inspector
- persistent top-left NIMM controls and a live AITAS strip

There are no separate current anthology/resources body tabs.

## Canonical runtime

Primary runtime artifacts:

- `data/anthology.json`
- `data/samras-txa.json`
- `data/samras-msn.json`
- `data/presentation/datum_icons.json`
- `private/daemon_state/data_workspace.json`

Deterministic anthology ordering remains:

- `layer -> value_group -> iteration`

Shared normalization lives in:

- `portals/_shared/portal/data_engine/anthology_normalization.py`

## Workbench behavior

Primary interaction model:

- default file attention is `anthology.json`
- `Navigate`, `Investigate`, `Mediate`, and `Manipulate` remain visible in the top-left workbench dock
- file focus uses AITAS `spacial = 1`
- datum focus uses AITAS `spacial = 2`
- file switching belongs to `Navigate`
- manipulate mode exposes create/delete at file focus and datum editing at datum focus

For SAMRAS-backed files (`samras-txa.json`, `samras-msn.json`):

- the workbench reads a structure-derived address tree, not an authoritative address map
- `POST /portal/api/data/system/mutate` accepts structure-aware SAMRAS actions for txa/msn
- generic `create_row` / `update_row` / `delete_row` are blocked for txa/msn so raw row edits cannot bypass canonical re-encoding
- sandbox SAMRAS workspaces derive address previews from structure and rewrite the governing magnitude on mutation

Canonical data endpoints:

- `POST /portal/api/data/system/selection_context`
- `GET /portal/api/data/system/resource_workbench`
- `POST /portal/api/data/system/mutate`
- `POST /portal/api/data/system/publish`
- `GET /portal/api/data/state`
- `POST /portal/api/data/directive`
- `GET /portal/api/data/anthology/table`
- `GET /portal/api/data/anthology/graph`
- `GET /portal/api/data/anthology/profile/<row_id>`
- `POST /portal/api/data/anthology/profile/update`
- `POST /portal/api/data/anthology/append`
- `POST /portal/api/data/anthology/delete`

The `system/*` routes define the current file-aware workbench. The anthology-specific routes remain active because the unified workbench still reuses anthology graph, profile, and direct-write behavior when attention is on anthology datums.

## MSS contract context role

The Data Tool is the selection and explanation surface for local contract context.

Canonical contract-edit workflow:

1. navigate to a canonical file or datum in `SYSTEM`
2. inspect a datum and its `abstraction_path` via the Details panel and anthology profile route when applicable
3. use those local datum refs as `owner_selected_refs` in `NETWORK > Contracts`
4. compile canonical `owner_mss` from the selected isolated closure

The Data Tool remains anthology-authoritative for anthology rows. Contract compilation lives in the shared MSS layer, not in the Data Tool itself.

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

Legacy query values such as `local_resources`, `inheritance`, `workbench=anthology`, and `workbench=resources` may still resolve for compatibility, but they are not part of the current visible `SYSTEM` workbench contract.
