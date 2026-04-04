# Analytics Tool

- Owns: analytics-specific backend/ui/contracts and the analytics state adapter.
- Does not own: generic shell rules or portal-global path derivation.
- Reads: analytics tool config/specs and instance-scoped analytics state.
- Writes: only analytics-scoped state under
  `private/utilities/tools/fnd-ebi/`.
- Depends on: `tools/_shared`, `mycite_core/state_machine`.
- Depended on by: FND analytics mediation surfaces.
