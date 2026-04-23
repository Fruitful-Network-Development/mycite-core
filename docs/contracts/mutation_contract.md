# Mutation Contract

## Status

Canonical

## Purpose

Define the shared mutation lifecycle contract so editable tool surfaces can stage, validate, preview, apply, and discard directive-driven changes without bypassing runtime authority.

## Canonical Lifecycle Actions

- `stage`
- `validate`
- `preview`
- `apply`
- `discard`

These actions are defined in `MyCiteV2/packages/state_machine/nimm/mutation_contract.py` and mapped to canonical endpoint shapes.

## Canonical Endpoint Shapes

- `POST /portal/api/v2/mutations/stage`
- `POST /portal/api/v2/mutations/validate`
- `POST /portal/api/v2/mutations/preview`
- `POST /portal/api/v2/mutations/apply`
- `POST /portal/api/v2/mutations/discard`

Tool-specific actions may continue to use existing routes during compatibility windows, but they should map semantically to these lifecycle actions.

## Canonical Payload Units

- `NimmDirective` schema: `mycite.v2.nimm.directive.v1`
- `NimmDirectiveEnvelope` schema: `mycite.v2.nimm.envelope.v1`
- `AitasContext` envelope fields:
  - `attention`
  - `intention`
  - `time`
  - `archetype`
  - `scope`

Example directive envelope:

```yaml
schema: mycite.v2.nimm.envelope.v1
directive:
  schema: mycite.v2.nimm.directive.v1
  verb: manipulate
  target_authority: cts_gis
  document_id: sandbox:cts_gis:sc.example.json
  aitas_ref: default
  targets:
    - file_key: sandbox:cts_gis:sc.example.json
      datum_address: 3-2-3-17-77-1
  payload:
    staged_values:
      - target:
          file_key: sandbox:cts_gis:sc.example.json
          datum_address: 3-2-3-17-77-1
        lens_id: trimmed_string
        canonical_value: MAIN STREET
        validation_issues: []
aitas:
  attention: ""
  intention: manipulate
  time: ""
  archetype: samras_nominal
  scope: sandbox
```

## Runtime Handler Boundary

Runtime implementations must expose one handler seam with explicit lifecycle methods:

- `stage(envelope)`
- `validate(envelope)`
- `preview(envelope)`
- `apply(envelope)`
- `discard(envelope)`

This seam is represented by `MutationContractRuntimeHandler` and keeps mutation orchestration in runtime, not in shell renderer code.

## Staging Boundary

`StagingArea` compiles staged values into a canonical manipulation directive envelope:

- stage values are lens-normalized display edits
- compiled directive verb is `manipulate`
- apply remains the only authoritative state mutation step

UI components may capture edits and dispatch action requests, but they must not perform authoritative writes directly.

Lens definition reference:

- lenses are stateless codecs with:
  - `decode(canonical_value)`
  - `encode(display_value)`
  - `validate_display(display_value)`
- staging always stores canonical values from lens `encode(...)`, not raw UI text.

## Compound Directive Projection

For operations that require both structure-space and datum-space intent, runtime may emit an additive compound directive projection:

- `schema`: `mycite.v2.nimm.compound.v1`
- `steps[0]`: structure-space mutation intent
- `steps[1]`: datum mutation directive

This projection is reflective metadata for preview/apply planning and does not bypass the apply-phase runtime authority boundary.
