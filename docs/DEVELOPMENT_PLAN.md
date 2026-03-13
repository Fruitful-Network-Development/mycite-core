# Development Plan

## Active baseline

Active runnable portals in this repo:

- `mycite-le_fnd`
- `mycite-le_tff`

Retired from active scope:

- `mycite-ne_mt`

## Current architectural direction

1. Keep the shared service-shell/runtime generic.
2. Keep the Data Tool as a core SYSTEM workbench surface.
3. Keep portal/network/data state file-backed rather than database-backed.
4. Make portal-specific tool/config/hosted/public-card authoring flow through per-portal `build.json`.
5. Keep anthology state-owned until the example/base abstraction stabilizes.

## Current implementation priorities

1. Stabilize the example portal anthology in `/srv/compose/portals/state/tff_portal/data/anthology.json`.
2. Continue network-engine hardening around request logs, contract verification, and reference inheritance.
3. Keep AWS and PayPal split by scope:
   - member-scoped tools
   - FND/platform-scoped tools
4. Consolidate duplicate helper/runtime patterns underneath those tools instead of merging the workflows.
5. Keep documentation canonical and remove time-stamped implementation clutter once folded into the main docs.

## Canonical references

- [`PORTAL_BUILD_SPEC.md`](PORTAL_BUILD_SPEC.md)
- [`TOOLS_SHELL.md`](TOOLS_SHELL.md)
- [`CANONICAL_DATA_ENGINE.md`](CANONICAL_DATA_ENGINE.md)
- [`NETWORK_PAGE_MODEL.md`](NETWORK_PAGE_MODEL.md)
- [`DATA_TOOL.md`](DATA_TOOL.md)
- [`REQUEST_LOG_V1.md`](REQUEST_LOG_V1.md)
- [`AWS_EMAILER_ABSTRACTION.md`](AWS_EMAILER_ABSTRACTION.md)
- [`PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md`](PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md)
- [`DATUM_MEDIATION_DEFAULTS.md`](DATUM_MEDIATION_DEFAULTS.md)
