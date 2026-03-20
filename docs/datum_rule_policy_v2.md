# Datum rule policy (v2)

Engine: `portals/_shared/portal/data_engine/rules/policy.py`  
Writes: `portals/_shared/portal/data_engine/rules/write_evaluation.py`

## Stance (frozen)

- **`invalid`** → blocked by default; optional `rule_write_override` for explicit admin path.
- **`ambiguous`** / **`unknown`** → **always writable** for normal users; classify + warn; do not require override.
- Staging/sandbox: understanding + policy always computed; **only invalid** blocks promotion/save to canonical stores unless override.

## Status → `RulePolicy` mapping

| Status | `write_allowed` | `requires_manual_override` | `ref_mode` | `lens_mode` | `can_publish` | `guidance_notes` |
|--------|-----------------|---------------------------|------------|-------------|---------------|------------------|
| `standard` | yes | no | `filtered_default` | `active` | yes | _(empty)_ |
| `transitional` | yes | no | `filtered_default` | `active` | no | transitional warnings |
| `ambiguous` | yes | no | `guided_prefer_filtered` | `degraded` | no | ambiguous / evolving |
| `unknown` | yes | no | `manual_default` | `none` | no | neutral/manual |
| `invalid` | no | yes | `blocked` | `error` | no | fix or override |

## Write consequences

- **Probe / append / profile / resource save**: graph must have `report.ok` (no invalid rows) unless `rule_write_override`.
- **Ambiguous / unknown rows**: add **warnings** via `graph_evolving_state_warnings()` and per-row `guidance_notes`; they do **not** set `graph_write_violation_message`.

## UI consequences

- **Standard / transitional**: default filtered reference picker when inference supplies `rule_key`; lens preview when `can_use_default_lens`.
- **Ambiguous**: distinct row shading (`ui_hints`); show `guidance_notes`; prefer filtered picker when API returns options; manual mode always available.
- **Unknown**: manual-first reference UX; show guidance; no family-specific lens.
- **Invalid**: error shading; save disabled unless user checks admin override (tooling choice).

## Reference picker

- **Default**: filtered lists from `POST .../rules/reference_filter` when `rule_key` or inference hints succeed.
- **Incomplete inference**: HTTP 400 on filter only when neither `rule_key` nor inferable hints exist — client should fall back to manual catalog (`ref_entry_mode=manual` + `rule_ref_manual_ack`) with warning, not block unrelated writes.
- **Ambiguous row**: `ref_mode` = `guided_prefer_filtered` — same endpoints; engine may return partial lists; freeform still allowed.

Schema: `mycite.portal.datum_rules.rule_policy.v2` (`to_dict`).
