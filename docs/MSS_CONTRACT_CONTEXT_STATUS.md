# MSS Contract Context Status

## Current state

The shared runtime now has a single MSS core under `portals/_shared/portal/mss/` and uses it as the contract context layer for NETWORK contract flows.

Current contract behavior:

- `owner_selected_refs` drives local compilation
- `owner_mss` stores the compiled local compact array
- `counterparty_mss` stores the remote compact array
- foreign datum refs resolve through the matching contract MSS context

The canonical contract editor is `NETWORK > Contracts`.

## Verified working behaviors

- local contract create/patch recompiles `owner_mss` from `owner_selected_refs`
- current canonical MSS payloads round-trip through compile/decode
- canonical writer now emits `wire_variant = canonical_v2` with dual-read support for older `canonical` payloads
- multi-datum selections create a synthetic `L+1-0-1` selection root
- archived reference fixture decoding is supported as `wire_variant = legacy_reference_fixture`
- anthology mutation paths now report `contract_mss_sync`
- local contracts with `owner_selected_refs` are recompiled after anthology compaction/VG0 sync
- selected refs are remapped when identifier compaction changes their addresses
- all currently shipped contract MSS bitstrings in the repo decode successfully under active dual-read paths (`canonical_v2`, prior `canonical`, and `legacy_reference_fixture`)
- Data Tool daemon endpoints remain available and separate from MSS contract resolution

## Verified gaps / constraints

- archived fixture support is read-only compatibility support, not the canonical local writer
- canonical_v2 metadata/stream semantics are aligned to the corrected compact-array reference model; archived fixture support remains decode-only compatibility
- manual `owner_mss` without `owner_selected_refs` is intentionally left untouched by anthology-driven recompilation
- contract editing remains on NETWORK; Utilities can link to it later, but there is no second canonical editor in this pass

## Migration status

- canonical local writes: active
- archived reference fixture dual-read: active
- current repo-seeded contract payloads in `build.json`: active with `owner_selected_refs`, `owner_mss`, and `counterparty_mss`
- daemon-backed NETWORK reference resolution wrapper: removed
- Data Tool daemon APIs: retained

## Direction

Next useful development steps:

1. add richer contract-editor datum picking UI directly from anthology table/profile data
2. expand legacy read compatibility only if more archived fixture families are discovered
3. add deeper UI explanations around abstraction paths and carry-over/COBM state
4. decide when temporary dual-read support can be retired once seeded/runtime data is fully canonical
