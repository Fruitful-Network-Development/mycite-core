# CTS-GIS Administrative Entity YAML Guidelines

This contract defines the canonical staged-insert format for CTS-GIS administrative datum inserts.

Use this format to prepare batches for upload into the CTS-GIS tool. Do not edit the database-backed administrative file through ad-hoc UI changes, and do not write the entries directly from an agent session.

## Canonical staged payload

The canonical schema is `mycite.v2.cts_gis.stage_insert.v1`.

```yaml
schema: mycite.v2.cts_gis.stage_insert.v1
document_id: sandbox:cts_gis:sc.example.json
document_name: sc.example.json
operation: insert_datums
datums:
  - family: administrative_street
    valueGroup: 2
    targetNodeAddress: 3-2-3-17-77-1
    title: "ASCII STREET NAME"
    references:
      - type: msn-samras
        nodeAddress: 3-2-3-17-77-1
      - type: title
        text: "ASCII STREET NAME"
```

JSON-equivalent support is allowed for the same structure, but YAML is the canonical operator-facing format.

## Ordering and MOS rules

- Every persisted datum address still uses `<layer>-<value_group>-<iteration>`.
- New street/admin-entity datums must use `valueGroup: 2`.
- Runtime computes final `iteration` values; operators do not stage final addresses directly.
- Same-city inserts must end with contiguous city-local `iteration` values. Do not leave gaps.
- Prepare and upload new entries grouped by city.
- Within the same immediate family, order entries by the magnitude of the first `msn-SAMRAS` reference before final iteration assignment.
- Reference order is canonicalized to:
  - `type: msn-samras`
  - `type: title`
- Title text is ASCII-normalized before apply.
- If a SAMRAS node does not yet have a stable label, a placeholder ASCII title is only allowed when the operator explicitly requests that warning-bearing path.
- Canonical persistence stays datum-row based even though the operator stages YAML first.

## Workflow

- Prepare the batch offline in YAML.
- Upload the YAML into the CTS-GIS tool, or convert the same structure to JSON for the same upload path.
- Let CTS-GIS `stage_insert_yaml` capture the temporary operator form in `tool_state.staged_insert`.
- Run `validate_stage` to normalize references, warnings, and the insertion plan.
- Run `preview_apply` to inspect affected rows, proposed inserted rows, final assigned addresses/iterations, and any remaps.
- Run `apply_stage` only after preview succeeds.
- Use `discard_stage` to clear staged intent without persistence.

The shell remains unchanged while this workflow runs: staged recap and legal verbs stay in the `directive_panel`, the staging widget lives in the existing Interface Panel body, and reflective preview/apply evidence stays in the workbench.
