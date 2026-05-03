# CTS-GIS ruigi-SAMRAS Structure

## Status

Canonical

## Purpose

This contract defines the `247-*` address space used by CTS-GIS precinct cohort profiles —
its identity, governing anchor datum addresses, how it is encoded in the tool document, and
how the runtime overlay engine matches precinct profiles to an AITAS attention node.

The ruigi address space (also spelled "ruiqi") is a SAMRAS namespace parallel to the `msn`
administrative namespace. Where `msn-SAMRAS` governs the `3-2-3-*` administrative node tree,
ruigi-SAMRAS governs the `247-<state>-<county>-<precinct>` precinct node tree.

---

## Address Space

### Form

```
247-<state>-<county>-<precinct>
```

Examples:

- `247-17-77-1`  (Ohio / Summit County / precinct 1)
- `247-17-77-100`
- `247-17-3-5`   (Ohio / Allen County / precinct 5)

### Ruiqi constant

`247` is the ruiqi addressing constant. It is the first segment of every ruigi address.

This constant is checked by the overlay engine as an integer:

```python
if precinct_parts[0] != 247:
    return False
```

where `precinct_parts = _address_tuple(node_id)`.

### State and county segments

- Segment 2 (`precinct_parts[1]`): matches `attention_parts[3]` from `3-2-3-<state>` attention
- Segment 3 (`precinct_parts[2]`): matches `attention_parts[4]` from `3-2-3-<state>-<county>` attention
- Segment 4+ (`precinct_parts[3+]`): precinct number(s), opaque to the overlay gate

---

## Anchor Datum Addresses

The ruigi-SAMRAS structure and its adjunct context are encoded in the CTS-GIS tool document
(`tool.<msn_id>.cts-gis.json`, located at `data/sandbox/cts-gis/`).

### Core ruigi-SAMRAS rows

| Datum address | Type reference | Label | Purpose |
|---------------|---------------|-------|---------|
| `1-1-4` | `0-0-5` | `SAMRAS-space-ruiqi` | Ruigi-SAMRAS magnitude bitstream (same type as msn-SAMRAS at `1-1-2`) |
| `2-0-3` | `~` (reference) | `SAMRAS-space-ruiqi` | Binding row — links `3-1-4` babelette to `1-1-4` space |
| `3-1-4` | `2-0-3` | `SAMRAS-babelette-ruiqi_id` | Babelette — governs how `247-*` node ids are attached to precinct rows |

### Chronological HOPS adjunct rows

Precinct cohort time windows are governed by the chronological HOPS adjunct:

| Datum address | Type reference | Label | Purpose |
|---------------|---------------|-------|---------|
| `1-1-5` | `0-0-1` | `HOPS-chornological` | Chronological HOPS magnitude bitstream |
| `2-0-4` | `~` (reference) | `HOPS-space-chornological` | Binding row — links `3-1-6` babelette to `1-1-5` space |
| `3-1-6` | `2-0-4` | `HOPS-babelette-UTC` | Babelette — governs chronological tokens on precinct time-window rows |

The runtime reads these via `_anchor_context_metadata()`:

```python
ruiqi_bits  = row_map["1-1-4"][2]         # non-empty → samras_ruiqi.present = True
chrono_bits = row_map["1-1-5"][2]         # non-empty → chronological_hops.present = True
```

`chronological_anchor_present` gates the full precinct overlay. When it is `True` and a
matching time context is active, precincts load as `summary_state: "loaded"`.

---

## Profile Key Schema (Precinct Source Files)

### File naming

Precinct source files in `data/sandbox/cts-gis/sources/precincts/` follow the staging form:

```
sc.<msn_id>.cts.<ruiqi_underscored>.json
```

Example: `sc.3-2-3-17-77-1-6-4-1-4.cts.247_17_77_1.json`

### Row schema: `7-3-1` precinct binding row

| Position | Reference | Meaning |
|----------|-----------|---------|
| col 1 | row address `7-3-1` | owner binding row |
| col 2 | `rf.3-1-4` | ruiqi babelette reference |
| col 3 | `247_17_77_1` | ruiqi precinct id (underscored form) |
| col 4 | `rf.3-1-5` | filament babelette reference |
| col 5 | ASCII-encoded precinct name | right-padded to 128 bits |
| col 6 | `6-0-1` | primary boundary collection |

The ruiqi id (`rf.3-1-4` column) is decoded via the `3-1-4` babelette (family
`SAMRAS-babelette-ruiqi_id`). The decoded value is stored in the profile index with
dashes substituted for underscores: `"247-17-77-1"`.

This is why the `profile_index` contains keys like `"247-17-77-1"` while the source file
name uses `"247_17_77_1"`.

---

## Overlay Matching Rule

`_precinct_profile_matches_attention` in `_overlay.py` governs which precinct profiles
load for a given AITAS attention node.

### State-level attention (`3-2-3-<state>`, length 4)

```python
if len(attention_parts) == 4 and tuple(attention_parts[:3]) == (3, 2, 3):
    return precinct_parts[1] == attention_parts[3]
```

All precincts whose state segment matches the attention state are in scope.
For `3-2-3-17` (Ohio), all `247-17-*-*` precincts match.

### County-level attention (`3-2-3-<state>-<county>`, length 5)

```python
if len(attention_parts) == 5 and tuple(attention_parts[:3]) == (3, 2, 3):
    return precinct_parts[1] == attention_parts[3] and precinct_parts[2] == attention_parts[4]
```

Only precincts in the matching county are in scope.
For `3-2-3-17-77` (Summit County), only `247-17-77-*` precincts match.

### Unsupported lineages

State/county attention must have prefix `3-2-3`. Any other lineage returns `False`.

---

## Timeframe Label Convention

District precinct collections are named from row labels on `6-0-*` collection rows in
the state or county profile source document. The runtime reads these via
`_district_timeframe_tokens()` which scans `row_views` for labels containing:
`"time_frame"`, `"district"`, `"present"`, or `"precinct_group"`.

### Example labels (Ohio state profile, `fnd.3-2-3-17.json`)

| Row | Label | Extracted token |
|-----|-------|----------------|
| `6-0-2` | `district_set_collection` | `"district_set_collection"` |

### Example labels (Summit County profile, `fnd.3-2-3-17-77.json`)

| Row | Label | Extracted token (source) |
|-----|-------|------------------------|
| Various | `23_present-district_31` | from county precinct-timeframe rows |
| Various | `applicable_time_frame` | from county precinct-timeframe rows |
| Various | `precinct_group-1` | from county precinct-timeframe rows |

The label `"23_present-district_31"` with token `state=loaded` and `precinct_count=371`
confirms 371 Summit County precincts are loaded when time context matches.

---

## Gate Logic

The precinct overlay is gated by `_precinct_overlay_gate_failures()`:

| Failure code | Cause |
|-------------|-------|
| `attention_node_missing` | No attention node set |
| `attention_lineage_unsupported` | Attention lineage is not `3-2-3-*` |
| `time_context_inactive` | `time_context_payload["active"] = False` |
| `chronological_anchor_missing` | `1-1-5` not in anchor document |
| `district_timeframe_mismatch` | Time token not found in profile's timeframe labels |

When `gate_failures = []`, the overlay loads precincts and `summary_state = "loaded"`.
When gate failures exist and overlay was requested, `summary_state = "blocked"`.
When not requested at all, `summary_state = "deferred"`.

---

## precinct_time_windows — Current Status and Path Forward

### Current live implementation

The system uses label-based timeframe detection (scanning `row_views` labels) rather than
a structured `precinct_time_windows` table. This works because precinct source files are
loaded into the in-memory `profile_index` and their time windows are encoded as row labels
on the associated state/county source document.

### Proposed DB table

The `precinct_time_windows` table schema is defined in
`docs/contracts/mos_database_schema_addendum.md`:

```sql
CREATE TABLE IF NOT EXISTS precinct_time_windows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    samras_namespace TEXT NOT NULL,
    ruigi_node_id TEXT NOT NULL,
    window_start_hops TEXT NOT NULL,
    window_end_hops TEXT NOT NULL,
    window_label TEXT NOT NULL,
    msn_id TEXT NOT NULL,
    scope_id TEXT NOT NULL DEFAULT 'fnd',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Migration status

The DB migration for this table belongs to the **MOS SQL catalog ingestion** track.
It is NOT a prerequisite for precinct overlay rendering. The live system operates correctly
without it as of 2026-05-03.

---

## Cross-References

| Document | Relationship |
|----------|-------------|
| `docs/contracts/cts_gis_samras_addressing.md` | msn-SAMRAS (parallel namespace, `1-1-2`) and adjunct context rows |
| `docs/contracts/cts_gis_precinct_cts_staging_sources.md` | Row-chain schema for precinct source files (`4→5→6→7`) |
| `docs/contracts/cts_gis_hops_profile_sources.md` | Source loading and overlay assembly rules |
| `docs/contracts/mos_database_schema_addendum.md` | `precinct_time_windows` SQL schema |
| `MyCiteV2/packages/modules/cross_domain/cts_gis/_overlay.py` | `_precinct_profile_matches_attention`, `_matching_precinct_profiles` |
| `MyCiteV2/packages/modules/cross_domain/cts_gis/service.py` | `_anchor_context_metadata` (reads `1-1-4`, `1-1-5`) |
