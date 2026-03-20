# Datum rule policy (v1)

Engine-owned behavior derived from `DatumUnderstanding.status` (and family/rule metadata).  
See `portals/_shared/portal/data_engine/rules/policy.py` for the frozen matrix.

## Status → operational meaning

| Status | `write_allowed` | `requires_manual_override` | `ref_mode` | `lens_mode` | Notes |
|--------|------------------|----------------------------|------------|-------------|-------|
| `standard` | yes | no | `filtered_default` | `active` | Normal edits; publish allowed |
| `transitional` | yes | no | `filtered_default` | `active` | Limited/edit warnings; publish blocked |
| `ambiguous` | no | yes | `blocked` | `degraded` | Use explicit `rule_write_override` (+ reason) to write |
| `invalid` | no | yes | `blocked` | `error` | Same override path |
| `unknown` | yes | no | `manual_default` | `none` | Neutral path; no family assumptions |

## API contract

- Write routes accept optional `rule_write_override` and `rule_write_override_reason`.
- Successful rule-aware responses include `datum_understanding` / `rule_policy` (or `rule_policy_by_id` on tables).
- `POST /portal/api/data/rules/reference_filter` infers `rule_key` when omitted (`value_group`, optional `magnitude_hint`, `parent_datum_id`).  
  `ref_entry_mode=manual` requires `rule_ref_manual_ack=true` and returns a full manual catalog.

## UI

Data tool consumes `datum_understanding` + `rule_policy_by_id` from `GET /portal/api/data/anthology/table` for row shading, family badges, and lens hints. Override controls are explicit (checkbox + reason).
