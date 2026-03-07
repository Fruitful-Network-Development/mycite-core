# mycite-core

Canonical source for the MyCite core portal framework and FND implementation.

## Scope

- Shared portal runtime and service-shell UI patterns.
- Core service routing (`/portal/home|data|network|tools|inbox`) and optional tool-package runtime contracts.
- Product/framework docs (NIMM/data model, progeny/profile cards, request-log/contracts).
- Active in-repo portal implementation: `portals/mycite-le_fnd`.

## Source of truth boundaries

- `mycite-core` owns portal framework code and core product docs.
- `srv-infra` owns server deployment, compose stacks, NGINX staging/promotion, and operational runbooks.

## Repository layout

- `portals/mycite-le_fnd/` canonical active portal implementation.
- `portals/_shared/` shared runtime and data-contract modules.
- `portals/assets/` shared icons/UI assets.
- `docs/` canonical framework documentation.
- `scripts/` maintenance/developer scripts.

## One-off instance archival

Legacy/example portal instance sources were removed from this repo and archived under:

- `/srv/compose/portals/unused_portal_sources/2026-03-07-fnd-only/`

## Canonical docs

- [`docs/TOOLS_SHELL.md`](docs/TOOLS_SHELL.md)
- [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md)
- [`docs/PROGENY_PROFILE_CARDS.md`](docs/PROGENY_PROFILE_CARDS.md)
- [`docs/request_log_and_contracts.md`](docs/request_log_and_contracts.md)
- [`docs/DATA_TOOL.md`](docs/DATA_TOOL.md)
- [`docs/TIME_SERIES_ABSTRACTION.md`](docs/TIME_SERIES_ABSTRACTION.md)
- [`docs/REQUEST_LOG_V1.md`](docs/REQUEST_LOG_V1.md)
- [`docs/AWS_EMAILER_ABSTRACTION.md`](docs/AWS_EMAILER_ABSTRACTION.md)
- [`docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md`](docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md)
- [`docs/DOCUMENTATION_POLICY.md`](docs/DOCUMENTATION_POLICY.md)
- [`docs/repo_policy.md`](docs/repo_policy.md)

## Infra report reference

Operational implementation reporting is canonical in:

- `/srv/repo/srv-infra/docs/fnd_portal_container_implementation_report.md`
