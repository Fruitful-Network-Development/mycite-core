# mycite-core

Canonical source for the MyCite portal framework.

## Scope

- Shared portal runtime and service-shell UI patterns (NE/LE).
- Core service routing (`/portal/home|data|network|tools|inbox`) plus optional tool-package runtime contracts.
- Product/framework docs (NIMM/data model, progeny/profile cards, contracts/request-log model).
- Portal instance source code under `portals/`.

## Source of truth boundaries

- `mycite-core` owns portal framework code and product docs.
- `srv-infra` owns server deployment, compose stacks, NGINX staging/promotion, and operational runbooks.

## Repository layout

- `portals/` portal implementations and example instances.
- `docs/` canonical framework documentation.
- `tools/` shared tool packages (when extracted).
- `scripts/` maintenance/developer scripts.

## Canonical docs

- [`docs/TOOLS_SHELL.md`](docs/TOOLS_SHELL.md)
- [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md)
- [`docs/PROGENY_PROFILE_CARDS.md`](docs/PROGENY_PROFILE_CARDS.md)
- [`docs/request_log_and_contracts.md`](docs/request_log_and_contracts.md)
- [`docs/DATA_TOOL.md`](docs/DATA_TOOL.md)
- [`docs/DATA_TOOL_ICONS.md`](docs/DATA_TOOL_ICONS.md)
- [`docs/DOCUMENTATION_POLICY.md`](docs/DOCUMENTATION_POLICY.md)
- [`docs/repo_policy.md`](docs/repo_policy.md)

## Infra report reference

Operational implementation reporting is canonical in:

- `/srv/repo/srv-infra/docs/fnd_portal_container_implementation_report.md`
