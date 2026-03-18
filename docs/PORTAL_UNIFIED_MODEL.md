# Portal Unified Model

## Goal

Portal runtime configuration is unified around neutral keys instead of hard-coding legal-entity-vs-individual split semantics.

Canonical config sections:

- `portal_profile`
- `portal_behavior`
- `portal_features`

## Compatibility

Legacy keys remain compatibility-readable:

- `organization_config`
- `organization_configuration`
- `orangization_configuration`
- `legal_entity_type`
- related `*_config_file` variants

Runtime reads can still consume these keys when present, but canonical writes should emit the unified model.

Compatibility observability:

- config write responses now include `compat_legacy_keys_used` when legacy keys are present in input payloads
- migration/report flows annotate legacy-source usage to support compatibility deprecation gates

## Write behavior

Config write canonicalization is handled in:

- `portals/_shared/portal/services/portal_model.py`
- `portals/_shared/runtime/flavors/fnd/portal/api/config.py`

Writes now normalize legacy shape into:

- `portal_profile.profile_kind`
- `portal_profile.organization_config_file`
- `portal_behavior.defaults`
- `portal_behavior.overrides`
- `portal_features.workflow_enabled`

Removal gate recommendation:

1. Monitor `compat_legacy_keys_used` and legacy-source migration warnings for at least one release cycle.
2. Only remove legacy-read fallbacks when telemetry shows no active legacy writes.

## Runtime behavior

TFF runtime behavior builders now prefer unified model fields first and fall back to legacy keys:

- organization config filename resolution
- default/override collection
- workflow model/profile kind selection
- workflow feature gate
