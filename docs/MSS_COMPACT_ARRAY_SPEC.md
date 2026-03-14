# MSS Compact Array Spec

## Summary

MSS is the compact-array form used to carry a scoped anthology context between portals without exposing a full `anthology.json`.

Canonical contract storage fields:

- `owner_selected_refs`
- `owner_mss`
- `counterparty_mss`

Canonical editing flow:

1. select local anthology datums
2. compile the isolated closure/path needed to interpret them
3. write the compiled raw bitstring to `owner_mss`
4. resolve foreign `<msn_id>.<datum>` refs through the matching contract MSS

The canonical editor lives at `NETWORK > Contracts`.

## Canonical wire shape

Canonical encoding remains `mycite.portal.mss.v1` with `encoding = cobm-layered-bitstring`.

High-level layout:

`<count_0_bits>1<number_of_bits><metadata><end_index_table><object_stream>`

Where:

- `<count_0_bits>1<number_of_bits>` is the width sentinel plus fixed-width payload size field
- `<metadata>` is the ordered set of MSS arrays:
  - `layer_count` / `layer_max`
  - `value_group_count_per_layer`
  - `iteration_count_per_value_group`
  - `value_group_value_per_value_group`
- `<end_index_table>` is the stop index table for the canonical object stream
- `<object_stream>` carries encoded row objects plus the per-layer COBM progression

Canonical metadata integers are self-delimiting binary values in the shared runtime implementation. The legacy archived fixture under `repo/mycite-core/mss/` is still readable, but it is not the writer used for new local contract saves.

## Row semantics

Datum identifiers remain:

- `<layer>-<value_group>-<iteration>`

Canonical MSS compiler rules:

- rows are compiled from the transitive local reference closure of `owner_selected_refs`
- rows are reindexed into an isolated anthology ordered by `layer -> value_group -> iteration`
- a multi-selection compile appends a synthetic selection-root row at `L+1-0-1`
- references are rewritten to the isolated anthology identifiers

Value-group rules:

- `VG0` is selection/carry-over style and stores references only
- `VG > 0` stores exactly `value_group` reference/magnitude tuples
- contract selection-root rows are `VG0`

## COBM and reference width

Canonical MSS uses COBM between layers so reference width is always determinable from the active carry-over set for the next layer.

For each layer transition:

1. accumulate the rows seen so far
2. record which accumulated identifiers are referenced by the next layer
3. write a COBM bit log in cumulative row order
4. use the active set size to determine the fixed reference width for the next layer

This is the canonical replacement for the ambiguity called out in the archived notes where tuple references and magnitudes could not otherwise be separated safely in a raw binary sequence.

## Contract behavior

Local contract rules:

- `owner_selected_refs` is the authoritative editable source
- `owner_mss` is the compiled artifact written from that selection when refs are present
- manual raw `owner_mss` is only preserved when `owner_selected_refs` is empty

Remote contract rules:

- `counterparty_mss` is stored as received
- remote MSS is dual-read and shown read-only in the editor

Foreign datum resolution:

- local refs resolve from the local anthology
- foreign refs resolve through the applicable contract MSS
- canonical ref syntax remains `<msn_id>.<datum>`

## Wire variants

Decoder responses expose `wire_variant`.

Current variants:

- `canonical`
  - current shared runtime writer output
- `legacy_reference_fixture`
  - the archived contract example under `repo/mycite-core/mss`

The archived fixture is kept as a reference/compatibility read target, not as the canonical writer format for new saves.

## Data-engine integration

Anthology mutations that can affect identifiers or closure must recompile local contracts with `owner_selected_refs` after anthology compaction and VG0 synchronization.

Current mutation surfaces:

- `/portal/api/data/anthology/append`
- `/portal/api/data/anthology/delete`
- `/portal/api/data/anthology/profile/update`
- time-series mutations that write anthology rows

Responses from those mutations now include `contract_mss_sync`.

## Archived references

Reference materials that informed the canonical model:

- `repo/mycite-core/mss/anthology-notes.txt`
- `repo/mycite-core/mss/MSS_convention.py`
- `repo/mycite-core/mss/msn-3-2-3-17-77-1-6-4-1-4.contract-3-2-3-17-77-2-6-3-1-6.json`

Those files are archived reference fixtures and notes. They are not the runtime source of truth for local contract writes.
