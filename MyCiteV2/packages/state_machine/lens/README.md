# Lens

Authority: stateless codec layer used at the staging boundary.

`packages/state_machine/lens/` defines display/canonical transforms that are intentionally separate from mutation decision logic.

## Contract

Every lens provides:

- `decode(canonical_value)` -> display value
- `encode(display_value)` -> canonical value
- `validate_display(display_value)` -> validation issue list

## Built-in Baselines

- `IdentityLens`
  - pass-through codec
- `TrimmedStringLens`
  - trims surrounding whitespace before staging canonical value

## Usage Pattern

1. UI captures display value.
2. Lens validates and encodes display value.
3. `StagingArea` stores encoded canonical value.
4. Staging compiler emits NIMM manipulation envelope.
5. Runtime lifecycle (`validate`/`preview`/`apply`) uses envelope as mutation intent.
