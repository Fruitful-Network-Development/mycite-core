# mycite-core

Canonical source for the MyCite core portal framework and runnable portal implementations.

## Scope

- Shared portal runtime and service-shell UI patterns.
- Core service routing (`/portal/system|network|utilities`) and compatibility redirects from legacy portal routes.
- Product/framework docs (NIMM/data model, progeny/profile cards, request-log/contracts).
- Active in-repo runnable portals:
  - `portals/mycite-le_fnd`
  - `portals/mycite-le_cvcc`
  - `portals/mycite-ne_mw`
  - `portals/mycite-ne_mt`
  - `portals/mycite-le_tff`

## Source of truth boundaries

- `mycite-core` owns portal framework code and core product docs.
- `srv-infra` owns server deployment, compose stacks, NGINX staging/promotion, and operational runbooks.

## Repository layout

- `portals/mycite-le_fnd/` FND portal.
- `portals/mycite-le_cvcc/` CVCC portal (board-member workspace owner surface).
- `portals/mycite-ne_mw/` MW portal.
- `portals/mycite-ne_mt/` MT portal.
- `portals/mycite-le_tff/` TFF portal (board-member workspace + workflow tab).
- `portals/_shared/` shared runtime and data-contract modules.
- `portals/assets/` shared icons/UI assets.
- `docs/` canonical framework documentation.
- `scripts/` maintenance/developer scripts.

## Local progeny and organization config model

Portal-local, non-secret entity scaffolding is stored under each portal `private/` tree:

- `private/network/aliases/`, `private/network/contracts/`, `private/network/request_log/`, `private/network/hosted.json`
- `private/network/progeny/{admin_progeny,member_progeny,user_progeny}/`
- `private/utilities/{tools,peripherals,vault}/`
- `private/config.json` canonical main portal profile and behavior source.
- `private/mycite-config-*.json` legacy fallback config shape (readable for compatibility).
- `organization_config.file_name` in main config selects the legal-entity profile.
- `organization_config.default_values` and `organization_config.added_values` compose portal behavior overrides.

Legacy root-private paths remain readable as fallbacks during rollout, but new writes target the canonical `private/network/*` and `private/utilities/*` trees.

## Canonical docs

- [`docs/TOOLS_SHELL.md`](docs/TOOLS_SHELL.md)
- [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md)
- [`docs/PROGENY_PROFILE_CARDS.md`](docs/PROGENY_PROFILE_CARDS.md)
- [`docs/REQUEST_LOG_V1.md`](docs/REQUEST_LOG_V1.md)
- [`docs/DATA_TOOL.md`](docs/DATA_TOOL.md)
- [`docs/TIME_SERIES_ABSTRACTION.md`](docs/TIME_SERIES_ABSTRACTION.md)
- [`docs/AWS_EMAILER_ABSTRACTION.md`](docs/AWS_EMAILER_ABSTRACTION.md)
- [`docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md`](docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md)
- [`docs/POC_WORKSPACE_MODEL.md`](docs/POC_WORKSPACE_MODEL.md)
- [`docs/DOCUMENTATION_POLICY.md`](docs/DOCUMENTATION_POLICY.md)
- [`docs/repo_policy.md`](docs/repo_policy.md)
- [`docs/PROGENY_CONFIG_MODEL.md`](docs/PROGENY_CONFIG_MODEL.md)
- [`docs/DATUM_MEDIATION_DEFAULTS.md`](docs/DATUM_MEDIATION_DEFAULTS.md)

## Terminology migration note

- Canonical portal-facing relationship term is `member`.
- Legacy `tenant` and `board_member` terms remain accepted for compatibility while runtime migrates incrementally.

## Infra report reference

Operational implementation reporting is canonical in:

- `/srv/repo/srv-infra/docs/fnd_portal_container_implementation_report.md`
