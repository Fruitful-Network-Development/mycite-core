# mycite-core

Canonical source for the MyCite portal framework, active portal implementations, and product documentation.

## Active runtime scope

Active runnable portals in this repo:

- `portals/mycite-le_example`
- `portals/mycite-le_fnd`
- `portals/mycite-le_tff`

Retired from active scope:

- `portals/mycite-ne_mt`

Placeholder/non-runnable directories should not be treated as active portal runtimes unless they regain an app/runtime surface.

## Source-of-truth boundaries

- Repo code lives under `/srv/repo/mycite-core`
- Live file-backed portal state lives under `/srv/compose/portals/state/<portal_instance>/`
- There is no application database in the portal runtime; state is JSON/ndjson/file backed
- Keycloak remains the only external database-backed identity system in scope

Example anthology currently being evolved as the base abstraction:

- `/srv/compose/portals/state/example_portal/data/anthology.json`

## Portal build model

Portal-specific authoring now starts from per-portal repo specs:

- `portals/mycite-le_example/build.json`
- `portals/mycite-le_fnd/build.json`
- `portals/mycite-le_tff/build.json`

Build specs are phase-1 authoritative for:

- enabled tools and mount behavior
- canonical private config payloads
- hosted payloads
- public profile/card payloads
- seed file lists for progeny/alias/profile scaffolding

Anthology remains state-owned in this phase. Build specs record anthology metadata/checksum only and do not overwrite anthology files during materialization.

Build/update script:

- `python3 portals/scripts/portal_build.py capture`
- `python3 portals/scripts/portal_build.py materialize`

## Repository layout

- `portals/_shared/` shared runtime, network, data-engine, and tool-loading modules
- `portals/assets/` shared icons/UI assets
- `portals/scripts/` portal build/update helpers
- `portals/mycite-le_example/` example/demo portal build spec
- `portals/mycite-le_fnd/` FND runtime
- `portals/mycite-le_tff/` TFF runtime
- `docs/` canonical product and runtime documentation

## Canonical docs

- [`docs/PORTAL_BUILD_SPEC.md`](docs/PORTAL_BUILD_SPEC.md)
- [`docs/TOOLS_SHELL.md`](docs/TOOLS_SHELL.md)
- [`docs/CANONICAL_DATA_ENGINE.md`](docs/CANONICAL_DATA_ENGINE.md)
- [`docs/NETWORK_PAGE_MODEL.md`](docs/NETWORK_PAGE_MODEL.md)
- [`docs/AWS_EMAILER_ABSTRACTION.md`](docs/AWS_EMAILER_ABSTRACTION.md)
- [`docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md`](docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md)
- [`docs/REQUEST_LOG_V1.md`](docs/REQUEST_LOG_V1.md)
- [`docs/PROGENY_PROFILE_CARDS.md`](docs/PROGENY_PROFILE_CARDS.md)
- [`docs/PROGENY_CONFIG_MODEL.md`](docs/PROGENY_CONFIG_MODEL.md)
- [`docs/DATA_TOOL.md`](docs/DATA_TOOL.md)
- [`docs/DOCUMENTATION_POLICY.md`](docs/DOCUMENTATION_POLICY.md)
- [`docs/repo_policy.md`](docs/repo_policy.md)

## Runtime note

Live FND/TFF containers are built from this repo through `/srv/compose/portals/docker-compose.yml`.

Do not edit running-container files directly. Update repo code/build specs, materialize state, then rebuild the target portal container.
