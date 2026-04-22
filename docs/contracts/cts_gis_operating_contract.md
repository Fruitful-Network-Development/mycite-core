# CTS-GIS Operating Contract

CTS-GIS now operates in two explicit runtime modes:

- `production_strict`
- `audit_forensic`

## Production Strict

`production_strict` is the default runtime expectation for stable tool operation.

- Runtime input is a compiled artifact only.
- Runtime does not run raw authority reconstruction or fallback repair.
- Runtime fails fast when compiled state is missing or invalid.
- Hot-path payload emphasizes:
  - `navigation_model`
  - `projection_model`
  - `evidence_model` (lazy/minimal unless explicitly requested)

Fail-fast state is projected as `compiled_cts_gis_state_invalid` and requires a compile step before standard interaction can continue.

## Audit Forensic

`audit_forensic` is the diagnostic pathway.

- Runtime may inspect raw sources and build reconstruction diagnostics.
- Runtime may emit expanded evidence payloads.
- Runtime may emit compatibility details to support migration and validation.

Audit mode should be used for corpus maintenance, not as the default production UI path.

## Compiled Artifact Authority

Compiled authority schema:

- `mycite.v2.portal.system.tools.cts_gis.compiled.v1`

Canonical artifact location:

- `data/payloads/compiled/cts_gis.<scope_id>.compiled.json`

The artifact records:

- canonical navigation model
- canonical projection model
- default tool state seed
- evidence snapshot
- invariant validity (`invariants.valid`)
- strict invariant validity (`strict_invariants.valid`) with one-authority and one-namespace checks

## Semantic Action Surface

CTS-GIS entries may include semantic actions in addition to compatibility `shell_request` payloads.

Canonical actions:

- `select_node`
- `set_intention`
- `set_time`
- `select_feature`
- `toggle_overlay`

The universal shell adapter may dispatch these actions directly while compatibility clients continue using `shell_request`.
