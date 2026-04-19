# CTS-GIS Precinct `.cts.` Staging Sources

## Status

Staged

## Purpose

These precinct source files are a staging corpus for the newer precinct-specific CTS-GIS datum shape.

They are stored under:

- `data/sandbox/cts-gis/sources/precincts/`

They are not yet the runtime Garland source contract. They exist so the precinct corpus can be materialized in repo-tracked datum form while the runtime integration catches up.

## File Shape

The staged files follow this naming pattern:

- `sc.3-2-3-17-77-1-6-4-1-4.cts.<ruiqi_underscored>.json`

Example:

- `sc.3-2-3-17-77-1-6-4-1-4.cts.247_17_77_1.json`

Each file carries:

- `anchor_file_version`
- `datum_addressing_abstraction_space`

## Row Chain

The precinct staging corpus uses a `4 -> 5 -> 6 -> 7` chain.

### `4-*` rows

- one closed polygon ring per row
- row address form: `4-<point_count>-<ring_seq>`
- coordinate values are stored as `rf.3-1-1` HOPS tokens
- ring closure is explicit in the stored row; if the GeoJSON ring is open, the starting point is appended before encoding

### `5-*` rows

- one polygon member per row
- row address form: `5-0-<polygon_seq>`
- references the `4-*` rows for that polygon in GeoJSON order

### `6-0-1`

- groups the polygon members for the file
- references all `5-*` rows in polygon order

### `7-3-1`

- precinct binding row
- uses `rf.3-1-4` for the staged Ruiqi precinct id
- uses `rf.3-1-5` for the precinct filament identifier
- points at `6-0-1`

## HOPS Encoding

The staged precinct corpus uses the same coordinate encoding convention as the existing Summit county/community source corpus:

- fixed prefix `3-76`
- `16` alternating base-100 partition segments
- longitude starts in `[-180, 180]`
- latitude starts in `[-90, 90]`
- each refinement appends one longitude bucket and one latitude bucket

This is sufficient to reproduce known Summit source tokens such as:

- `3-76-27-73-3-3-51-5-68-54-77-92-68-85-42-43-67-71`

## Filament Identifier

For the staged `setA` precinct corpus:

- `rf.3-1-5` is built from `PrecinctNa`
- characters are encoded as ASCII 8-bit binary
- the result is right-padded with `0` bits to exactly `128` bits

Example:

- `AK01-A` -> `010000010100101100110000001100010010110101000001` plus right-padding to `128` bits
