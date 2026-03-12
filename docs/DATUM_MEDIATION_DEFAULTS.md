# Datum Mediation Defaults

Shared mediation defaults are implemented in `portals/_shared/portal/mediation/`.

## Purpose

Provide a shared typed mediation layer that converts stored `reference` + `magnitude`
values into user-facing values (and back) without portal-instance-specific decode logic.

## Canonical Registry Contract

Each registry entry defines:

- `matcher_rule`
- `matcher`
- `decode`
- `encode`
- `validate_magnitude`
- `validate_value`
- `render_hint`

Public registry helpers:

- `resolve_entry(standard_id)`
- `list_registry_entries()`
- compatibility wrappers: `decode_value(...)`, `encode_value(...)`

## Default Standard IDs

Canonical IDs:

- `boolean_ref`
- `ascii_char`
- `dns_wire_format`
- `text_byte_format`
- `timestamp_unix_s`
- `duration_s`
- `length_m`
- `coordinate`

Compatibility aliases are preserved (for example `boolean`, `char`, `ascii`, `text_byte_email_format`, `time_span_s`, `coordinate_fixed_hex`).

## Response Shape

- `ok`
- `standard_id`
- `reference`
- `magnitude`
- `value`
- `display`
- `warnings`
- `errors`

## Notes

- Unknown standards are non-fatal and return raw values with warnings.
- Validation warnings/errors are merged into decode/encode results.
- Coordinate mediation supports fixed-width hex split decoding used by geography/spatial foundations.
