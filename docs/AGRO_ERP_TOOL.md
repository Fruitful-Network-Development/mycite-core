# AGRO ERP Tool (TFF)

## Purpose

`AGRO ERP` is an optional portal tool package for resolving property coordinate tokens with an anthology-aware daemon workflow.

It is designed for the current TFF phase where config may contain:

- raw coordinate hex tokens, or
- datum identifiers that resolve to hex magnitude values in `data/anthology.json`.

## Routes

- `GET /portal/tools/agro_erp/home`
- `GET /portal/tools/agro_erp/model.json`
- `POST /portal/tools/agro_erp/daemon/resolve`

## Daemon definitions

The tool defines two daemon entrypoints:

- `property_geometry` -> `property.geometry.coordinates`
- `property_bbox` -> `property.bbox`

Each daemon exposes a NIMM-style directive payload (`action`, `subject`, `method`, AITAS args) and resolves tokens to coordinate pairs.

Resolution path prefers canonical engine mediation (`daemon_resolve_tokens`) when available and falls back to local decoding only as compatibility behavior.

## Coordinate decoding contract

For each token:

1. split fixed-width hex into equal upper/lower halves
2. interpret each half as signed two's-complement
3. divide by `1e7`
4. map to `[longitude, latitude]`

Example:

- `CF69268F1894171F` -> `[-81.5192433000000, 41.2358431000000]`

## Runtime inputs

- active private config (`private/config.json`, legacy fallback supported)
- anthology payload (`data/anthology.json`)

## Enablement

Set in active private config:

```json
"enabled_tools": ["config_schema", "agro_erp"]
```
