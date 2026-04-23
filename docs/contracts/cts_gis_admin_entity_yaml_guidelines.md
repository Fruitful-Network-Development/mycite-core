# CTS-GIS Administrative Entity YAML Guidelines

This note defines the temporary offline preparation format for adding new `msn_id`-associated datum entries to the CTS-GIS administrative entity file.

Use this format to prepare batches for upload into the CTS-GIS tool. Do not edit the database-backed administrative file through ad-hoc UI changes, and do not write the entries directly from an agent session.

## Address and ordering rules

- Every datum address uses `<layer>-<value_group>-<iteration>`.
- New street datums should use `valueGroup: 2`.
- `iteration` values must stay contiguous for each city. Do not leave gaps.
- Prepare and upload new entries grouped by city, starting from the highest existing `iteration` for that city and appending sequentially.
- Within the same immediate family, order entries by the magnitude of the first `msn-SAMRAS` reference before assigning final `iteration` values.
- If a SAMRAS node does not yet have a stable label, use a placeholder ASCII title and replace it later through the same upload workflow.
- The ordering and reference rules must be preserved so the MOS schema remains valid.

## YAML preparation format

```yaml
datums:
  - valueGroup: 2
    iteration: 23
    references:
      - type: msn-samras
        nodeAddress: 0x1234
      - type: title
        text: "Main Street"
  - valueGroup: 2
    iteration: 24
    references:
      - type: msn-samras
        nodeAddress: 0x5678
      - type: title
        text: "Oak Avenue"
```

Rules for each item:

- The first `references` entry must be the `msn-SAMRAS` node reference:
  - `type: msn-samras`
  - `nodeAddress: <magnitude>`
- The second `references` entry must be the ASCII title:
  - `type: title`
  - `text: "<Street Name>"`

## Recommended workflow

- Prepare the batch offline in YAML.
- Validate city grouping, contiguous `iteration` values, and `msn-SAMRAS` ordering before upload.
- Upload the YAML into the CTS-GIS tool, or convert the same structure to JSON for the same upload path.
- Let the tool's script-backed directive flow apply the change so interface-panel operations can remain conventionalized while preserving the MOS schema rule set.

This YAML form is intentionally temporary. It exists to hold structured datum-insertion intent for CTS-GIS administrative updates until the tool-side upload and execution flow is fully formalized.
